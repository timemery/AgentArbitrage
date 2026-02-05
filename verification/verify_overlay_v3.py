from playwright.sync_api import sync_playwright, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Login
        print("Navigating to login...")
        page.goto("http://localhost:5000/")

        login_btn = page.get_by_role("button", name="Log In", exact=True)
        if login_btn.is_visible():
             print("Clicking Log In button...")
             login_btn.click()

        print("Waiting for username input...")
        page.wait_for_selector("input[name='username']", state="visible")

        print("Filling credentials...")
        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")

        print("Submitting form...")
        page.click("button[type='submit']")

        # 2. Go to Dashboard
        print("Navigating to dashboard...")
        page.wait_for_url("**/dashboard")

        # 3. Wait for table stability
        print("Waiting for table row...")
        # Wait for the table to be visible
        page.wait_for_selector("#deals-table", state="visible")

        # Wait for at least one row
        page.wait_for_selector(".deal-row", state="visible")

        # 4. Click row to open overlay (Use locator directly to ensure freshness)
        print("Clicking row...")
        # Try to click the specific test deal if available
        test_deal = page.locator("tr[data-asin='TESTASIN99']")
        if test_deal.count() > 0:
            print("Found Test Deal row, clicking...")
            test_deal.click()
        else:
            print("Test Deal not found, clicking first row...")
            page.locator(".deal-row").first.click()

        # 5. Wait for overlay
        print("Waiting for overlay...")
        page.wait_for_selector("#deal-overlay", state="visible")

        # 6. Hover over title to check truncated effect
        print("Hovering over title...")
        page.hover("#overlay-title")

        # Wait a bit for hover effect
        page.wait_for_timeout(500)

        # 7. Take screenshot
        print("Taking screenshot...")
        page.screenshot(path="verification/overlay_v3.png")

        browser.close()

if __name__ == "__main__":
    run()
