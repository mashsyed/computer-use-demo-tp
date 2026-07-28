# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.models import Gemini
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset
from google.genai import types

from .playwright import PlaywrightComputer

# Setup Google Cloud Project environment variables
try:
    _, project_id = google.auth.default()
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    pass

os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
if os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from google.adk.models.llm_response import LlmResponse
import re

class NonStreamingGemini(Gemini):
    async def generate_content_async(self, llm_request, stream=False):
        # Diagnostic file logging
        try:
            with open("/Users/mashsyed/.gemini/antigravity/scratch/computer-use-demo-tp/app/debug.log", "a") as f:
                f.write("\n=== NEW CALL ===\n")
                f.write(f"contents count: {len(llm_request.contents) if llm_request.contents else 0}\n")
                if llm_request.contents:
                    for idx, content in enumerate(llm_request.contents):
                        f.write(f"Content {idx}: role={content.role}\n")
                        if content.parts:
                            for p_idx, part in enumerate(content.parts):
                                text_val = part.text if part.text else ""
                                f.write(f"  Part {p_idx}: text='{text_val}', function_call={part.function_call is not None}, function_response={part.function_response is not None}\n")
        except Exception as ex:
            pass

        # 1. Intercept simple greetings to prevent triggering high-overhead browser automation
        user_text = ""
        if llm_request.contents:
            for content in reversed(llm_request.contents):
                if content.role != "model" and content.parts:
                    # Also make sure this content is a text message, not a tool response
                    if any(part.text for part in content.parts):
                        for part in content.parts:
                            if part.text:
                                user_text += part.text
                        break

        clean_text = re.sub(r'[^\w\s]', '', user_text.lower().strip())
        greetings = {"hello", "hi", "hey", "hello there", "hi there", "greetings"}
        if clean_text in greetings:
            part = types.Part.from_text(
                text="Hello! I am your Mercedes-Benz Talent Acquisition Portal assistant. "
                     "How can I help you automate your talent acquisition workflows today?"
            )
            content = types.Content(parts=[part], role="model")
            yield LlmResponse(content=content)
            return

        # 2. Force streaming off because gemini-2.5-computer-use-preview-10-2025 
        # throws a 400 ClientError: "UI actions are not enabled for streaming API."
        prompt_tokens = 0
        candidates_tokens = 0
        total_tokens = 0
        action_summary = "Unknown Action"

        async for response in super().generate_content_async(llm_request, stream=False):
            if response.usage_metadata:
                prompt_tokens = response.usage_metadata.prompt_token_count or 0
                candidates_tokens = response.usage_metadata.candidates_token_count or 0
                total_tokens = response.usage_metadata.total_token_count or 0
            
            # Extract the actual action (tool name + arguments or text response)
            if response.content and response.content.parts:
                func_calls = []
                text_snippet = ""
                for part in response.content.parts:
                    if part.function_call:
                        args_str = ", ".join(f"{k}={v}" for k, v in part.function_call.args.items()) if part.function_call.args else ""
                        func_calls.append(f"{part.function_call.name}({args_str})")
                    elif part.text and not part.text.isspace():
                        text_snippet = part.text.strip().replace("\n", " ").replace("\r", " ")[:60]
                
                if func_calls:
                    action_summary = " | ".join(func_calls)
                elif text_snippet:
                    action_summary = text_snippet
                else:
                    action_summary = "Text Response"
            
            yield response

        if total_tokens > 0:
            # Gemini 2.5 Computer Use Pro-tier pricing:
            # Input <= 200k: $1.25 / 1M tokens ($0.00000125 per token)
            # Output <= 200k: $10.00 / 1M tokens ($0.00001000 per token)
            input_rate = 0.00000125 if prompt_tokens <= 200000 else 0.00000250
            output_rate = 0.00001000 if candidates_tokens <= 200000 else 0.00001500
            
            input_cost = prompt_tokens * input_rate
            output_cost = candidates_tokens * output_rate
            call_cost = input_cost + output_cost

            try:
                # 1. Write to standard text audit log
                log_path = "/Users/mashsyed/.gemini/antigravity/scratch/computer-use-demo-tp/app/session_costs.log"
                with open(log_path, "a") as f:
                    f.write(f"--- LLM Call --- \n")
                    f.write(f"  Action:        {action_summary}\n")
                    f.write(f"  Input Tokens:  {prompt_tokens:,}\n")
                    f.write(f"  Output Tokens: {candidates_tokens:,}\n")
                    f.write(f"  Total Tokens:  {total_tokens:,}\n")
                    f.write(f"  Estimated Cost: ${call_cost:.6f} USD\n\n")
                
                # 2. Write to structured CSV log for data analysis
                import csv
                import datetime
                
                csv_path = "/Users/mashsyed/.gemini/antigravity/scratch/computer-use-demo-tp/app/session_costs.csv"
                file_exists = os.path.exists(csv_path)
                
                with open(csv_path, mode="a", newline="") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow([
                            "timestamp", 
                            "action",
                            "prompt_tokens", 
                            "candidates_tokens", 
                            "total_tokens", 
                            "input_cost_usd", 
                            "output_cost_usd", 
                            "total_cost_usd"
                        ])
                    
                    writer.writerow([
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        action_summary,
                        prompt_tokens,
                        candidates_tokens,
                        total_tokens,
                        f"{input_cost:.8f}",
                        f"{output_cost:.8f}",
                        f"{call_cost:.8f}"
                    ])
                
                print(f"\n💵 [COST TRACKER] Call used {total_tokens:,} tokens ({prompt_tokens:,} input, {candidates_tokens:,} output). Estimated Cost: ${call_cost:.6f} USD\n", flush=True)
            except Exception:
                pass

MODEL_ID = os.environ.get("MODEL_ID", "gemini-2.5-computer-use-preview-10-2025")

# Define the root agent with ComputerUse capability
root_agent = Agent(
    name="mercedes_portal_agent",
    model=NonStreamingGemini(
        model=MODEL_ID,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
    instruction=(
        "You are an expert browser automation agent specializing in talent acquisition workflows "
        "on the Mercedes-Benz Talent Acquisition Portal.\n\n"
        "CONVERSATIONAL RULES:\n"
        "1. If the user is just greeting you (e.g., saying 'hello', 'hi'), asking general questions, "
        "or discussing non-browser tasks, respond politely with text ONLY. Do NOT call any tools or open the browser.\n"
        "2. Only initiate browser automation and call computer use tools if the user explicitly requests a task "
        "that requires interacting with the portal or web browser.\n\n"
        "CRITICAL TOOL CALLING RULES (when performing browser tasks):\n"
        "1. You must interact with the computer using ONLY the registered tools.\n"
        "2. To click, use `click_at(x, y)` (do NOT use `click`).\n"
        "3. To type text, use `type_text_at(x, y, text)` (do NOT use `type`).\n"
        "4. To hover, use `hover_at(x, y)` (do NOT use `hover`).\n"
        "5. You must call `open_web_browser` first to initialize your viewport and load the portal."
    ),
    tools=[
        ComputerUseToolset(computer=PlaywrightComputer(screen_size=(960, 1080)))
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
    context_cache_config=ContextCacheConfig(),
)
