
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Set the base URL from an environment variable, defaulting to localhost
        base_url = os.environ.get("BASE_URL", "http://127.0.0.1:5000")

        # Create the verification directory if it doesn't exist
        os.makedirs("/home/jules/verification", exist_ok=True)

        try:
            # 0. Reset session state for the test user
            print("Resetting test user state...")
            # We need to perform a POST request to the reset endpoint.
            # Playwright's page.request can do this.
            await page.request.post(f"{base_url}/reset_test_user_state")
            print("Test user state reset.")

            # 1. Login
            print("Navigating to login page...")
            await page.goto(f"{base_url}/")
            print("Revealing login form...")
            # Click the initial button to show the form
            await page.get_by_role("button", name="Log In").click()
            print("Logging in...")
            await page.get_by_placeholder("Username").fill("tester")
            await page.get_by_placeholder("Password").fill("OnceUponaBurgerTree-12monkeys")
            await page.locator("form[action='/login'] >> text=Log In").click()
            await page.wait_for_url(f"{base_url}/guided_learning")
            print("Login successful.")

            # 2. Trigger Restriction Check
            print("Navigating to settings page...")
            await page.goto(f"{base_url}/settings")
            print("Clicking 'Connect' button...")
            await page.get_by_role("button", name="Connect Your Amazon Account").click()
            # Wait for the confirmation message to appear
            await page.wait_for_selector("text=Successfully connected your Amazon Seller Account!")
            print("Connection triggered successfully.")

            # 3. Verify Dashboard
            print("Navigating to dashboard...")
            await page.goto(f"{base_url}/dashboard")
            print("Waiting for dashboard to render...")

            # Wait for a specific, reliable element that indicates the table has been populated.
            # We'll wait for one of our test book titles to appear.
            await page.wait_for_selector("text=Test Book 1 - Pending")
            print("Dashboard data loaded.")

            # Optional: Add a small delay for any final UI updates
            await asyncio.sleep(2)

            print("Taking screenshot of the dashboard...")
            screenshot_path = "/home/jules/verification/dashboard_gated_column.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred: {e}")
            error_screenshot_path = "/home/jules/verification/error_screenshot.png"
            await page.screenshot(path=error_screenshot_path)
            print(f"Error screenshot saved to {error_screenshot_path}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
