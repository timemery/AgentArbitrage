import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to login
        try:
            await page.goto("http://localhost:5000/login", timeout=5000)
            # Check if redirected to index (login page is at / but has login modal)
            if page.url.endswith("/dashboard"):
                print("Already logged in.")
            else:
                # Login manually
                # Login button is .login-button on index
                if await page.locator(".login-button").is_visible():
                     await page.click(".login-button")
                     await page.wait_for_selector(".login-form", state="visible")
                     await page.fill("input[name='username']", "tester")
                     await page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
                     await page.click(".login-form button")
                     await page.wait_for_url("**/dashboard")
                else:
                    # Maybe we are on login route via POST? No, we visited GET /login which is 405.
                    # Start at root
                    await page.goto("http://localhost:5000/")
                    await page.click(".login-button")
                    await page.wait_for_selector(".login-form", state="visible")
                    await page.fill("input[name='username']", "tester")
                    await page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
                    await page.click(".login-form button")
                    await page.wait_for_url("**/dashboard")

        except Exception as e:
            print(f"Login flow error: {e}")

        # Now check dashboard CSS
        try:
            await page.goto("http://localhost:5000/dashboard")
            await page.wait_for_selector("#deals-table")

            # 1. Group Header Top
            group_header = page.locator("#deals-table .group-header th").first
            # We need to wait for computed style to stabilize (sticky logic might delay?)
            # Just read it.
            group_top = await group_header.evaluate("el => getComputedStyle(el).top")
            print(f"Group Header Top: {group_top}")

            # 2. Column Header Top
            col_header = page.locator("#deals-table tr.column-header-row th").first
            col_top = await col_header.evaluate("el => getComputedStyle(el).top")
            print(f"Column Header Top: {col_top}")

            # 3. Sort Arrows Top and Height
            sort_cell = page.locator("#deals-table tr.sort-arrows-row td").first
            sort_top = await sort_cell.evaluate("el => getComputedStyle(el).top")
            sort_height = await sort_cell.evaluate("el => getComputedStyle(el).height")
            print(f"Sort Row Top: {sort_top}, Height: {sort_height}")

            # 4. Shadow Line Top
            shadow = page.locator("#sticky-header-shadow-line")
            shadow_top = await shadow.evaluate("el => getComputedStyle(el).top")
            print(f"Shadow Line Top: {shadow_top}")

            # 5. Check background color transparency of TH (to confirm blocker logic)
            # If logic is correct, TH background is transparent (rgba(0, 0, 0, 0))
            col_bg = await col_header.evaluate("el => getComputedStyle(el).backgroundColor")
            print(f"Column Header BG: {col_bg}")

            # Check for ::before blocker
            # We can't easily select pseudo elements with playwright locators,
            # but we can evaluate JS
            before_bg = await col_header.evaluate("el => getComputedStyle(el, '::before').backgroundColor")
            print(f"Column Header ::before BG: {before_bg}")

            after_bg = await col_header.evaluate("el => getComputedStyle(el, '::after').backgroundColor")
            print(f"Column Header ::after BG: {after_bg}")

        except Exception as e:
            print(f"Verification failed: {e}")

        await browser.close()

asyncio.run(run())
