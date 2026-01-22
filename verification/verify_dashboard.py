import time
from playwright.sync_api import sync_playwright

def test_dashboard_sticky_headers():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Login
        page.goto("http://localhost:5000/")

        # Click the "Log In" button to show the form first
        page.click("button.login-button")

        # Use simple selectors for the login form inputs based on the HTML
        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
        page.click("button[type='submit']")

        # Go to Dashboard
        page.wait_for_load_state("networkidle")
        if "/dashboard" not in page.url:
            page.goto("http://localhost:5000/dashboard")

        # Wait for table to load
        page.wait_for_selector("#deals-table table", timeout=20000)

        # 1. Capture Top State (Static)
        time.sleep(1)
        page.screenshot(path="verification/dashboard_top_static.png", clip={'x': 0, 'y': 0, 'width': 1920, 'height': 400})

        # 2. Scroll down to trigger sticky headers
        # Scroll enough to move the table up but keep headers sticky
        # Filter Bottom is ~177px. Scroll 200px.
        page.evaluate("window.scrollTo(0, 250)")

        # Wait a bit for transition
        time.sleep(2)

        # Take screenshot of the header area
        page.screenshot(path="verification/dashboard_scrolled_sticky.png", clip={'x': 0, 'y': 0, 'width': 1920, 'height': 400})

        browser.close()

if __name__ == "__main__":
    try:
        test_dashboard_sticky_headers()
        print("Verification script ran successfully.")
    except Exception as e:
        print(f"Verification script failed: {e}")
