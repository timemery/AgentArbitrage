from playwright.sync_api import sync_playwright, expect
import time

def verify_refresh_janitor_removed():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Login
        print("Logging in...")
        page.goto("http://localhost:5000/")

        # The button that toggles the form has text "Log In"
        # The submit button also has text "Log In"
        # We need to distinguish them.
        # The toggle button class is "login-button"
        # The submit button is inside the form

        page.locator("button.login-button").click()

        # Now wait for form to be visible? The class 'show-form' is added to container

        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")

        # Submit
        page.locator("form.login-form button[type='submit']").click()

        # Should redirect to guided_learning for admin, but we want dashboard
        print("Navigating to dashboard...")
        page.goto("http://localhost:5000/dashboard")

        # 2. Setup Network Interception
        janitor_called = False

        def handle_route(route):
            nonlocal janitor_called
            if "/api/run-janitor" in route.request.url:
                janitor_called = True
                print("ERROR: /api/run-janitor was called!")
            route.continue_()

        # Monitor network requests
        page.route("**/*", handle_route)

        # 3. Click Refresh Deals
        print("Clicking Refresh Deals...")

        # Make sure the table is rendered or at least the button is there
        refresh_link = page.locator("#refresh-deals-link")
        refresh_link.wait_for(state="visible")
        refresh_link.click()

        # 4. Verify UI Feedback
        # Wait a bit for any potential network calls to fire
        # And ensure the refresh text changes or at least verify fetchDeals was called (implicit by no error?)

        page.wait_for_timeout(3000)

        # 5. Assertions
        if janitor_called:
            print("FAILURE: Janitor API was triggered.")
            exit(1)
        else:
            print("SUCCESS: Janitor API was NOT triggered.")

        page.screenshot(path="verification/refresh_dashboard.png")
        print("Screenshot saved to verification/refresh_dashboard.png")

        browser.close()

if __name__ == "__main__":
    verify_refresh_janitor_removed()
