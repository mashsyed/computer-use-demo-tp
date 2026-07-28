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

import asyncio
import logging
import os
from typing import Literal, Optional, Any

from google.adk.tools.computer_use.base_computer import BaseComputer, ComputerEnvironment
from google.adk.tools.computer_use.computer_use_tool import ComputerState
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


def start_mock_server(directory: str):
    """Start a lightweight background HTTP server on a dynamically allocated free port."""
    import socket
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    server = HTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    logger.info(f"📡 Local HTTP server started on http://127.0.0.1:{port} serving {directory}")
    return server, port


class PlaywrightComputer(BaseComputer):
    """A robust Playwright-based computer driver implementation for ADK's Computer Use Toolset."""

    def __init__(self, screen_size: tuple[int, int] = (960, 1080)):
        self._screen_width, self._screen_height = screen_size
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.server = None
        self.server_port = None

    async def initialize(self) -> None:
        """Initialize the Playwright browser and launch local mock servers if needed."""
        logger.info("Initializing PlaywrightComputer...")
        self.playwright = await async_playwright().start()
        
        headless_mode = os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes")
        self.browser = await self.playwright.chromium.launch(headless=headless_mode)
        
        self.context = await self.browser.new_context(accept_downloads=True)
        self.page = await self.context.new_page()
        await self.page.set_viewport_size({"width": self._screen_width, "height": self._screen_height})

        # Setup automated download handler to save downloads locally
        async def handle_download(download):
            download_path = os.path.join(os.getcwd(), download.suggested_filename)
            await download.save_as(download_path)
            logger.info(f"📥 [DOWNLOAD] Saved downloaded file to: {download_path}")
            
        self.page.on("download", handle_download)

        # Automatically start the local http server to serve index.html / mock_store.html
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.server, self.server_port = start_mock_server(directory=script_dir)

        # Setup route handler to transparently map mock domains to the local server
        async def route_handler(route, request):
            url = request.url
            if "mercedes-talent.com" in url:
                new_url = url.replace("mercedes-talent.com", f"127.0.0.1:{self.server_port}")
                await route.continue_(url=new_url)
            elif "google-store-mock.com" in url:
                new_url = url.replace("google-store-mock.com", f"127.0.0.1:{self.server_port}")
                await route.continue_(url=new_url)
            else:
                await route.continue_()

        await self.context.route("**/*", route_handler)

    async def screen_size(self) -> tuple[int, int]:
        return self._screen_width, self._screen_height

    async def open_web_browser(self) -> ComputerState:
        """Opens the browser by navigating to Google or local mock server."""
        use_mercedes = os.environ.get("USE_MERCEDES_PORTAL", "true").lower() in ("true", "1", "yes")
        use_mock_store = os.environ.get("USE_MOCK_STORE", "false").lower() in ("true", "1", "yes")

        if use_mercedes:
            url = "http://mercedes-talent.com/index.html"
        elif use_mock_store:
            url = "http://google-store-mock.com/mock_store.html"
        else:
            url = "https://www.google.com"

        return await self.navigate(url)

    async def click_at(self, x: int, y: int) -> ComputerState:
        logger.info(f"Clicking at real coordinates: ({x}, {y})")
        await self.page.mouse.click(x, y)
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def hover_at(self, x: int, y: int) -> ComputerState:
        logger.info(f"Hovering at coordinates: ({x}, {y})")
        await self.page.mouse.move(x, y)
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool = True,
        clear_before_typing: bool = True,
    ) -> ComputerState:
        logger.info(f"Typing text '{text}' at ({x}, {y})")
        await self.page.mouse.click(x, y)
        await asyncio.sleep(0.1)
        
        if clear_before_typing:
            # Select all and delete to clear existing text
            await self.page.keyboard.press("Meta+A")
            await self.page.keyboard.press("Backspace")
            
        await self.page.keyboard.type(text)
        if press_enter:
            await self.page.keyboard.press("Enter")
            
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def scroll_document(self, direction: Literal["up", "down", "left", "right"]) -> ComputerState:
        logger.info(f"Scrolling document: {direction}")
        scroll_amount = 500
        if direction == "up":
            await self.page.evaluate(f"window.scrollBy(0, -{scroll_amount})")
        elif direction == "down":
            await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        elif direction == "left":
            await self.page.evaluate(f"window.scrollBy(-{scroll_amount}, 0)")
        elif direction == "right":
            await self.page.evaluate(f"window.scrollBy({scroll_amount}, 0)")
            
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def scroll_at(
        self,
        x: int,
        y: int,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int,
    ) -> ComputerState:
        logger.info(f"Scrolling at ({x}, {y}) direction: {direction} magnitude: {magnitude}")
        await self.page.mouse.move(x, y)
        
        delta_x = 0
        delta_y = 0
        if direction == "up":
            delta_y = -magnitude
        elif direction == "down":
            delta_y = magnitude
        elif direction == "left":
            delta_x = -magnitude
        elif direction == "right":
            delta_x = magnitude
            
        await self.page.mouse.wheel(delta_x, delta_y)
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def wait(self, seconds: int) -> ComputerState:
        logger.info(f"Waiting for {seconds} seconds...")
        await asyncio.sleep(seconds)
        return await self.current_state()

    async def go_back(self) -> ComputerState:
        logger.info("Going back...")
        await self.page.go_back()
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def go_forward(self) -> ComputerState:
        logger.info("Going forward...")
        await self.page.go_forward()
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def search(self) -> ComputerState:
        logger.info("Searching (navigating to Google)...")
        return await self.navigate("https://www.google.com")

    async def navigate(self, url: str) -> ComputerState:
        logger.info(f"Navigating to: {url}")
        
        # Intercept and map port 8000 or localhost/127.0.0.1 to local mock server port if running
        if "127.0.0.1:8000" in url or "localhost:8000" in url:
            if self.server_port is not None and self.server_port != 8000:
                url = url.replace("127.0.0.1:8000", f"127.0.0.1:{self.server_port}")
                url = url.replace("localhost:8000", f"127.0.0.1:{self.server_port}")
                
        await self.page.goto(url)
        await self.page.wait_for_timeout(1000)
        return await self.current_state()

    async def key_combination(self, keys: list[str]) -> ComputerState:
        key_str = "+".join(keys)
        logger.info(f"Pressing key combination: {key_str}")
        await self.page.keyboard.press(key_str)
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def drag_and_drop(
        self, x: int, y: int, destination_x: int, destination_y: int
    ) -> ComputerState:
        logger.info(f"Dragging from ({x}, {y}) to ({destination_x}, {destination_y})")
        await self.page.mouse.move(x, y)
        await self.page.mouse.down()
        await self.page.mouse.move(destination_x, destination_y)
        await self.page.mouse.up()
        await self.page.wait_for_timeout(500)
        return await self.current_state()

    async def current_state(self) -> ComputerState:
        screenshot_bytes = await self.page.screenshot(type="png")
        current_url = self.page.url
        return ComputerState(screenshot=screenshot_bytes, url=current_url)

    async def click(self, x: int, y: int, intent: Optional[str] = None) -> ComputerState:
        """Alias for click_at to support standard computer use tool calling."""
        return await self.click_at(x, y)

    async def hover(self, x: int, y: int, intent: Optional[str] = None) -> ComputerState:
        """Alias for hover_at to support standard computer use tool calling."""
        return await self.hover_at(x, y)

    async def type(self, x: int, y: int, text: str, intent: Optional[str] = None) -> ComputerState:
        """Alias for type_text_at to support standard computer use tool calling."""
        return await self.type_text_at(x, y, text)

    async def close(self) -> None:
        logger.info("Closing PlaywrightComputer browser...")
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.server:
            self.server.shutdown()

    async def environment(self) -> ComputerEnvironment:
        return ComputerEnvironment.ENVIRONMENT_BROWSER
