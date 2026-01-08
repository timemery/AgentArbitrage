from playwright.sync_api import sync_playwright
import time
import os

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to dashboard...")
        try:
            # Login first
            page.goto("http://localhost:5000/")

            # Click the Log In button to show the form
            if page.locator(".login-button").is_visible():
                print("Clicking Log In toggle...")
                page.click(".login-button")
                page.wait_for_selector(".login-form", state="visible")

            if page.locator("input[name='username']").is_visible():
                print("Logging in...")
                page.fill("input[name='username']", "tester")
                page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle")

            # Navigate to dashboard if not already there
            if "/dashboard" not in page.url:
                 page.goto("http://localhost:5000/dashboard")

            print("Waiting for table headers...")
            # Wait specifically for the group headers we modified
            page.wait_for_selector("th:text('Supply & Demand')")

            # Take screenshot of the table area
            print("Taking screenshot...")
            page.locator(".table-container").screenshot(path="verification/dashboard_headers.png")

            print("Screenshot saved to verification/dashboard_headers.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
