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
        # Note: The login logic in wsgi_handler.py redirects 'tester' (admin) to /guided_learning
        # We need to manually navigate to /dashboard after login if the redirect goes elsewhere
        page.wait_for_load_state("networkidle")
        if "/dashboard" not in page.url:
            page.goto("http://localhost:5000/dashboard")

        # Wait for table to load
        page.wait_for_selector("#deals-table table", timeout=20000)

        # Scroll down to trigger sticky headers
        # We need to scroll enough to pass the filter panel (134px + 43px = 177px)
        page.evaluate("window.scrollTo(0, 500)")

        # Wait a bit for transition
        time.sleep(2)

        # Take screenshot of the header area
        # We focus on the top part of the viewport where sticky headers are
        page.screenshot(path="verification/dashboard_sticky_headers.png", clip={'x': 0, 'y': 0, 'width': 1920, 'height': 400})

        browser.close()

if __name__ == "__main__":
    try:
        test_dashboard_sticky_headers()
        print("Verification script ran successfully.")
    except Exception as e:
        print(f"Verification script failed: {e}")
