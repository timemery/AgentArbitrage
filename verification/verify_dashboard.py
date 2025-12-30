from playwright.sync_api import sync_playwright

def verify_dashboard_filters():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Login
        page.goto("http://localhost:5000/")

        # Click the login toggle button first to make the form visible
        page.click(".login-button")

        page.fill("input[name='username']", "AristotleLogic")
        page.fill("input[name='password']", "virtueLiesInGoldenMean")
        page.click("button[type='submit']")

        # 2. Wait for dashboard
        page.wait_for_selector(".dashboard-content-wrapper")

        # 3. Verify Filters exist
        assert page.is_visible("label[for='profit_confidence_slider']")
        assert page.is_visible("label[for='seller_trust_slider']")
        assert page.is_visible("label[for='profit_slider']")
        assert page.is_visible("label[for='percent_down_slider']")

        # 4. Interact with sliders
        # Set Profit Confidence to 50%
        page.fill("input#profit_confidence_slider", "50")
        page.dispatch_event("input#profit_confidence_slider", "input")

        # Set Seller Trust to 80%
        page.fill("input#seller_trust_slider", "80")
        page.dispatch_event("input#seller_trust_slider", "input")

        # 5. Apply Filters
        page.click("button[type='submit']")

        # Wait for reload (simulated by checking if deal counter or table updates,
        # but since DB is empty/static test data, we just wait a bit for visual snapshot)
        page.wait_for_timeout(2000)

        # 6. Screenshot
        page.screenshot(path="verification/dashboard_filters.png", full_page=True)
        print("Screenshot saved to verification/dashboard_filters.png")

        browser.close()

if __name__ == "__main__":
    try:
        verify_dashboard_filters()
    except Exception as e:
        print(f"Verification failed: {e}")
