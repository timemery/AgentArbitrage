import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to home
        try:
            await page.goto("http://localhost:5000")
        except Exception as e:
            print(f"Failed to connect: {e}")
            await browser.close()
            return

        # Login flow
        try:
            # Click Login button to show form
            await page.click(".login-button")
            await page.wait_for_selector(".login-form", state="visible")

            # Fill form
            await page.fill("input[name='username']", "Admin")
            await page.fill("input[name='password']", "admin")

            # Submit
            await page.click(".login-form button")

            # Wait for dashboard
            await page.wait_for_selector("#deals-table", timeout=10000)
            print("Login successful, Dashboard loaded.")

        except Exception as e:
            print(f"Login failed: {e}")
            # If we are already on dashboard (no login needed?), check for table
            if await page.query_selector("#deals-table"):
                print("Already on dashboard.")
            else:
                await browser.close()
                return

        # Check CSS values for sticky headers

        # 1. Group Header Top
        group_header = page.locator("#deals-table .group-header th").first
        group_top = await group_header.evaluate("el => getComputedStyle(el).top")
        print(f"Group Header Top: {group_top}")

        # 2. Column Header Top
        col_header = page.locator("#deals-table .column-header-row th").first
        col_top = await col_header.evaluate("el => getComputedStyle(el).top")
        print(f"Column Header Top: {col_top}")

        # 3. Sort Arrows Top and Height
        sort_cell = page.locator("#deals-table .sort-arrows-row td").first
        sort_top = await sort_cell.evaluate("el => getComputedStyle(el).top")
        sort_height = await sort_cell.evaluate("el => getComputedStyle(el).height")
        print(f"Sort Row Top: {sort_top}, Height: {sort_height}")

        # 4. Shadow Line Top
        shadow = page.locator("#sticky-header-shadow-line")
        shadow_top = await shadow.evaluate("el => getComputedStyle(el).top")
        print(f"Shadow Line Top: {shadow_top}")

        # Verify Pseudo elements existence (indirectly via screenshot or just assuming if CSS matches)
        # We can check if background-color is transparent
        col_bg = await col_header.evaluate("el => getComputedStyle(el).backgroundColor")
        print(f"Column Header BG (Should be transparent/rgba(0,0,0,0)): {col_bg}")

        await browser.close()

asyncio.run(run())
