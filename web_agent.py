#  Copyright 2025 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import asyncio
import logging
import os

from google import genai
from google.genai.types import (
    ComputerUse,
    Content,
    Environment,
    FinishReason,
    FunctionResponse,
    FunctionResponseBlob,
    FunctionResponsePart,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    Tool,
)
from playwright.async_api import Page, async_playwright

logging.getLogger("google_genai._common").setLevel(logging.ERROR)

# --- CONFIGURATION ---
# Load configuration from environment variables for best practice.
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_LOCATION", "global")
MODEL_ID = os.environ.get("MODEL_ID", "gemini-3.5-flash")


# --- HELPER FUNCTIONS  ---


def normalize_x(x: int, screen_width: int) -> int:
    """Convert normalized x coordinate (0-1000) to actual pixel coordinate."""
    return int(x / 1000 * screen_width)


def normalize_y(y: int, screen_height: int) -> int:
    """Convert normalized y coordinate (0-1000) to actual pixel coordinate."""
    return int(y / 1000 * screen_height)


def start_mock_server(directory=None):
    """Start a lightweight background HTTP server on a dynamically allocated free port."""
    import socket
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    
    if directory:
        handler = partial(SimpleHTTPRequestHandler, directory=directory)
    else:
        handler = SimpleHTTPRequestHandler
    
    server = HTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print(f"📡 Local HTTP server started on http://127.0.0.1:{port} serving {directory or 'current directory'}")
    return server, port


async def execute_function_calls(
    response, page: Page, screen_width: int, screen_height: int
) -> tuple[
    str, list[tuple[str, str, bool]]
]:  # <-- Note the added bool for safety status
    """Extracts and executes function calls from the model response."""
    await asyncio.sleep(0.1)

    function_calls = [
        part.function_call
        for part in response.candidates[0].content.parts
        if hasattr(part, "function_call") and part.function_call
    ]

    thoughts = [
        part.text
        for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ]

    if thoughts:
        print(f"🤔 Model Reasoning: {' '.join(thoughts)}")

    if not function_calls:
        return "NO_ACTION", []

    results = []
    for function_call in function_calls:
        result = None
        safety_acknowledged = False

        safety_decision = function_call.args.get("safety_decision")
        if (
            safety_decision
            and safety_decision.get("decision") == "require_confirmation"
        ):
            print(f"\n⚠️ SAFETY PROMPT: {safety_decision.get('explanation')}")
            user_input = input(
                f"Allow the agent to execute '{function_call.name}'? (y/n): "
            )

            if user_input.strip().lower() not in ["y", "yes"]:
                print("🚫 Action denied by user.")
                results.append((function_call.name, "user_denied", False))
                continue  # Skip execution and move to the next function call

            print("✅ Action approved.")
            safety_acknowledged = True

        print(f"⚡ Executing Action: {function_call.name}")
        try:
            if function_call.name == "open_web_browser":
                result = "success"  # The browser is already open
            elif function_call.name == "navigate":
                await page.goto(function_call.args["url"])
                await page.wait_for_timeout(1000)  # Give renderer 1s to paint page
                result = "success"
            elif function_call.name in ["click_at", "click"]:
                raw_x = function_call.args["x"]
                raw_y = function_call.args["y"]
                actual_x = normalize_x(raw_x, screen_width)
                actual_y = normalize_y(raw_y, screen_height)
                print(f"[DEBUG] Click at: raw=({raw_x}, {raw_y}), actual=({actual_x}, {actual_y})")
                await page.mouse.click(actual_x, actual_y)
                await page.wait_for_timeout(500)  # Give renderer 500ms to paint click effects/transitions
                result = "success"
            elif function_call.name in ["type_text_at", "type"]:
                text_to_type = function_call.args["text"]
                raw_x = function_call.args["x"]
                raw_y = function_call.args["y"]
                actual_x = normalize_x(raw_x, screen_width)
                actual_y = normalize_y(raw_y, screen_height)
                print(f'[DEBUG] Typing text "{text_to_type}" at raw=({raw_x}, {raw_y}), actual=({actual_x}, {actual_y})')
                await page.mouse.click(actual_x, actual_y)
                await asyncio.sleep(0.1)
                await page.keyboard.type(text_to_type)
                if function_call.args.get("press_enter", False):
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(500)  # Give renderer 500ms to paint input text/submission transitions
                result = "success"
            else:
                result = "unknown_function"
        except Exception as e:
            print(f"❗️ Error executing {function_call.name}: {e}")
            result = f"error: {e!s}"

        results.append((function_call.name, result, safety_acknowledged))

    return "CONTINUE", results


# --- THE AGENT LOOP ---


async def agent_loop(initial_prompt: str, max_turns: int = 20) -> None:
    """Main agent loop for local execution with a browser."""
    if not PROJECT_ID:
        raise ValueError("GOOGLE_PROJECT_ID environment variable not set.")

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    browser = None
    try:
        async with async_playwright() as p:
            # Launch browser (allowing headless override via environment variable)
            headless_mode = os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes")
            browser = await p.chromium.launch(headless=headless_mode)
            page = await browser.new_page(accept_downloads=True)
            sw, sh = 960, 1080
            await page.set_viewport_size({"width": sw, "height": sh})
            
            # Setup automated download handler to save downloads locally
            async def handle_download(download):
                download_path = os.path.join(os.getcwd(), download.suggested_filename)
                await download.save_as(download_path)
                print(f"📥 [DOWNLOAD] Saved downloaded file to: {download_path}")
            page.on("download", handle_download)
            use_mercedes = os.environ.get("USE_MERCEDES_PORTAL", "false").lower() in ("true", "1", "yes")
            use_mock_store = os.environ.get("USE_MOCK_STORE", "true").lower() in ("true", "1", "yes")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if use_mercedes:
                server, port = start_mock_server(directory=script_dir)
                portal_url = f"http://127.0.0.1:{port}/index.html"
                initial_prompt = initial_prompt.replace("http://127.0.0.1:8000", portal_url)
                initial_prompt = initial_prompt.replace("http://localhost:8000", portal_url)
                initial_prompt = initial_prompt.replace("the Mercedes-Benz portal", f"the Mercedes-Benz portal ({portal_url})")
            elif use_mock_store:
                server, port = start_mock_server(directory=script_dir)
                mock_url = f"http://127.0.0.1:{port}/mock_store.html"
                initial_prompt = initial_prompt.replace("the Google Store webpage", f"the Google Store webpage ({mock_url})")
            else:
                initial_prompt = initial_prompt.replace("the Google Store webpage", "the Google Store webpage (https://store.google.com/?hl=en-US)")

            await page.goto("https://www.google.com")

            print(f"🎬 Starting Agent Loop with prompt: '{initial_prompt}'")

            # Configure Computer Use tool with browser environment
            # Base configuration for the Computer Use tool
            config_kwargs = {
                "tools": [
                    Tool(
                        computer_use=ComputerUse(
                            environment=Environment.ENVIRONMENT_BROWSER,
                            # Optional: Exclude specific predefined functions
                            excluded_predefined_functions=["drag_and_drop"],
                        )
                    )
                ]
            }

            # Conditionally add thinking_config only for the Gemini 3 models
            model_version = float(MODEL_ID.split("-")[1])
            if model_version >= 3:
                config_kwargs["thinking_config"] = ThinkingConfig(include_thoughts=True)

            config = GenerateContentConfig(**config_kwargs)

            screenshot = await page.screenshot(type="png")
            contents = [
                Content(
                    role="user",
                    parts=[
                        Part(text=initial_prompt),
                        Part.from_bytes(data=screenshot, mime_type="image/png"),
                    ],
                )
            ]
            for turn in range(max_turns):
                print(f"\n--- 🔁 Turn {turn + 1} ---")
                print(f"[DEBUG] Calling generate_content with model={MODEL_ID}")
                print(f"[DEBUG] Config: {config}")
                print(f"[DEBUG] Contents length: {len(contents)}")
                for i, content in enumerate(contents):
                    print(f"  [DEBUG] Content {i} role={content.role}")
                    for j, part in enumerate(content.parts):
                        if hasattr(part, "text") and part.text:
                            print(f"    [DEBUG] Part {j} text: '{part.text}'")
                        elif hasattr(part, "inline_data") and part.inline_data:
                            print(f"    [DEBUG] Part {j} inline_data mime_type: {part.inline_data.mime_type}, data size: {len(part.inline_data.data)}")

                response = client.models.generate_content(
                    model=MODEL_ID, contents=contents, config=config
                )

                if not response.candidates:
                    print("❗️ Model returned no candidates. Terminating loop.")
                    print("Full Response:", response)
                    break

                if response.candidates[0].finish_reason == FinishReason.SAFETY:
                    print(
                        "🛑 SAFETY TRIGGERED: The model halted execution due to safety policies."
                    )
                    print(f"Details: {response.candidates[0].safety_ratings}")
                    break

                print(
                    f"[DEBUG] Model Finish Reason: {response.candidates[0].finish_reason}"
                )
                contents.append(response.candidates[0].content)
                print("[DEBUG] Appended model response to history.")

                # Check if the attribute exists AND is not None
                active_function_calls = [
                    part.function_call
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "function_call") and part.function_call
                ]

                if not active_function_calls:
                    final_text = "".join(
                        part.text
                        for part in response.candidates[0].content.parts
                        if hasattr(part, "text") and part.text is not None
                    )
                    if final_text:
                        print(f"✅ Agent Finished: {final_text}")
                        break

                status, execution_results = await execute_function_calls(
                    response, page, sw, sh
                )
                print(
                    f"[DEBUG] Execution Results: status='{status}', results={execution_results}"
                )

                if status == "NO_ACTION":
                    continue

                function_response_parts = []
                # Unpack the variables returned by our function
                for name, result, safety_acknowledged in execution_results:
                    # Capture screenshot in standard PNG format for model vision
                    screenshot_png = await page.screenshot(type="png")
                    current_url = page.url

                    # Prepare the response payload
                    response_payload = {"url": current_url}

                    # Handle the safety and denial states
                    if result == "user_denied":
                        response_payload["error"] = "user_denied"
                    elif safety_acknowledged:
                        # CRITICAL: Acknowledge the safety decision so the API doesn't throw an error
                        response_payload["safety_acknowledgement"] = True

                    # 1. Add the SDK-required FunctionResponse part (including the nested PNG screenshot)
                    function_response_parts.append(
                        Part(
                            function_response=FunctionResponse(
                                name=name,
                                response=response_payload,
                                parts=[
                                    FunctionResponsePart(
                                        inline_data=FunctionResponseBlob(
                                            mime_type="image/png", data=screenshot_png
                                        )
                                    )
                                ],
                            )
                        )
                    )

                contents.append(Content(role="user", parts=function_response_parts))
                print(f"📝 State captured. History now has {len(contents)} messages.")
    finally:
        if browser:
            await browser.close()
            print("\n--- Browser closed. ---")


class Tee:
    def __init__(self, filename, mode="w", stream=None):
        self.file = open(filename, mode, encoding="utf-8")
        self.stream = stream

    def write(self, data):
        self.file.write(data)
        self.file.flush()
        if self.stream:
            self.stream.write(data)
            self.stream.flush()

    def flush(self):
        self.file.flush()
        if self.stream:
            self.stream.flush()


# --- SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    import sys
    import os

    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_run.log")
    sys.stdout = Tee(log_file_path, "w", sys.stdout)
    sys.stderr = Tee(log_file_path, "w", sys.stderr)

    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    else:
        prompt = "Navigate to the Google Store and find the page of 'Pixel 10'."

    asyncio.run(agent_loop(prompt))
