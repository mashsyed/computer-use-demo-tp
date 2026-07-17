import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Load local index.html under the exact 960x1080 computer use viewport size
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        sw, sh = 960, 1080
        await page.set_viewport_size({"width": sw, "height": sh})
        
        html_path = os.path.abspath("index.html")
        await page.goto(f"file://{html_path}")
        await page.wait_for_timeout(500) # Let it render fully

        print("--- Coordinates on Login Page ---")
        
        # Email Input
        email_box = await page.locator("#username-input").bounding_box()
        if email_box:
            ex, ey = email_box['x'] + email_box['width'] / 2, email_box['y'] + email_box['height'] / 2
            print(f"📍 Recruiter Email Input (#username-input): x={ex:.1f}, y={ey:.1f} | width={email_box['width']:.1f}, height={email_box['height']:.1f}")
        
        # Password Input
        pass_box = await page.locator("#password-input").bounding_box()
        if pass_box:
            px, py = pass_box['x'] + pass_box['width'] / 2, pass_box['y'] + pass_box['height'] / 2
            print(f"📍 Password Input (#password-input): x={px:.1f}, y={py:.1f} | width={pass_box['width']:.1f}, height={pass_box['height']:.1f}")
            
        # Login Button
        btn_box = await page.locator("#btn-login").bounding_box()
        if btn_box:
            bx, by = btn_box['x'] + btn_box['width'] / 2, btn_box['y'] + btn_box['height'] / 2
            print(f"📍 Authenticate Button (#btn-login): x={bx:.1f}, y={by:.1f} | width={btn_box['width']:.1f}, height={btn_box['height']:.1f}")

        # Fill and Submit Login to access Report view
        await page.fill("#username-input", "recruiter@mercedes-benz.com")
        await page.fill("#password-input", "PremiumCareer2026")
        await page.click("#btn-login")
        await page.wait_for_timeout(800) # Let view transition animation complete

        print("\n--- Coordinates on Report Export Page ---")
        
        # Starting Date Input
        start_box = await page.locator("#starting-date").bounding_box()
        if start_box:
            sx, sy = start_box['x'] + start_box['width'] / 2, start_box['y'] + start_box['height'] / 2
            print(f"📍 Starting Date Input (#starting-date): x={sx:.1f}, y={sy:.1f} | width={start_box['width']:.1f}, height={start_box['height']:.1f}")

        # Ending Date Input
        end_box = await page.locator("#ending-date").bounding_box()
        if end_box:
            enx, eny = end_box['x'] + end_box['width'] / 2, end_box['y'] + end_box['height'] / 2
            print(f"📍 Ending Date Input (#ending-date): x={enx:.1f}, y={eny:.1f} | width={end_box['width']:.1f}, height={end_box['height']:.1f}")
            
        # Download Button
        dl_box = await page.locator("#btn-download-csv").bounding_box()
        if dl_box:
            dx, dy = dl_box['x'] + dl_box['width'] / 2, dl_box['y'] + dl_box['height'] / 2
            print(f"📍 Download CSV Button (#btn-download-csv): x={dx:.1f}, y={dy:.1f} | width={dl_box['width']:.1f}, height={dl_box['height']:.1f}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
