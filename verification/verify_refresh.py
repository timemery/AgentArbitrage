from playwright.sync_api import sync_playwright, expect
import time
import os

def run_verification():
    os.makedirs("verification", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login
        print("Navigating to login...")
        page.goto("http://localhost:5000/")

        # Click toggle button
        print("Clicking login toggle...")
        page.click("button.login-button")

        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
        page.click("button[type='submit']")

        # Check login success
        print("Waiting for redirect...")
        page.wait_for_url("**/guided_learning")

        # Go to Dashboard
        print("Navigating to dashboard...")
        page.goto("http://localhost:5000/dashboard")

        # Verify Refresh Link exists
        refresh_link = page.locator("#refresh-deals-link")
        expect(refresh_link).to_be_visible()
        expect(refresh_link).to_have_text("⟳ Refresh Deals")

        print("Taking initial screenshot...")
        page.screenshot(path="verification/1_initial.png")

        # Click Refresh
        print("Clicking refresh...")
        refresh_link.click()

        # Verify text changes to "Refreshing..."
        # It might be fast, so use expect with timeout
        expect(refresh_link).to_have_text("⟳ Refreshing...")
        print("Taking refreshing screenshot...")
        page.screenshot(path="verification/2_refreshing.png")

        # Wait for it to revert
        print("Waiting for revert...")
        expect(refresh_link).to_have_text("⟳ Refresh Deals", timeout=10000)
        print("Taking final screenshot...")
        page.screenshot(path="verification/3_final.png")

        browser.close()
        print("Verification complete.")

if __name__ == "__main__":
    run_verification()
