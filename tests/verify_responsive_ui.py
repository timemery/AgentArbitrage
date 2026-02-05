from playwright.sync_api import Page, expect, sync_playwright
import time

def test_responsive_layout(page: Page):
    print("Navigating to home...")
    page.goto("http://localhost:5000/")
    print(f"Page Title: {page.title()}")

    # Login if redirected to login page
    if "Agent Arbitrage" in page.title() and "Dashboard" not in page.title():
        print("On Home Page. Attempting Login...")

        # Click the initial 'Log In' button to reveal the form
        # Use specific locator if possible to avoid ambiguity
        toggle_btn = page.locator(".login-button")
        if toggle_btn.is_visible():
            print("Clicking Toggle Button...")
            toggle_btn.click()

        # Fill form
        print("Filling credentials...")
        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")

        # Click the submit button inside the form
        print("Submitting form...")
        page.locator(".login-form button").click()

        # Wait for navigation
        page.wait_for_url("**/dashboard")
        print("Navigated to Dashboard.")

    print(f"Current URL: {page.url}")
    print(f"Page Title: {page.title()}")

    # Verify Table Exists
    print("Waiting for table...")
    expect(page.locator("#deals-table")).to_be_visible(timeout=10000)

    # Check for rows
    row_count = page.locator(".deal-row").count()
    print(f"Found {row_count} rows.")
    if row_count == 0:
        print("No deals found. Check database population.")
        # Print body text to see if there's an error message
        print(page.locator("body").inner_text())

    expect(page.get_by_text("Test Book Title")).to_be_visible()

    # 2. Test 1200px (Desktop)
    print("Testing 1200px...")
    page.set_viewport_size({"width": 1200, "height": 800})
    time.sleep(1) # wait for layout
    page.screenshot(path="/home/jules/verification/1200_desktop.png")

    # Assert ASIN visible
    # Check if .col-asin has display: none
    asin_cell = page.locator(".col-asin").first
    expect(asin_cell).to_be_visible()

    # 3. Test 1000px (Tablet - Hide ASIN)
    print("Testing 1000px...")
    page.set_viewport_size({"width": 1000, "height": 800})
    time.sleep(1)
    page.screenshot(path="/home/jules/verification/1000_tablet.png")

    # Assert ASIN HIDDEN
    # In Playwright, if CSS hides it, to_be_visible() returns False.
    expect(asin_cell).not_to_be_visible()

    # 4. Test 800px (Truncation)
    print("Testing 800px...")
    page.set_viewport_size({"width": 800, "height": 800})
    time.sleep(1)
    page.screenshot(path="/home/jules/verification/800_narrow.png")

    # 5. Test 600px (Mobile - Hide Trust)
    print("Testing 600px...")
    page.set_viewport_size({"width": 600, "height": 800})
    time.sleep(1)
    page.screenshot(path="/home/jules/verification/600_mobile.png")

    trust_cell = page.locator(".col-seller-quality-score").first
    expect(trust_cell).not_to_be_visible()

    print("All checks passed!")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_responsive_layout(page)
        except Exception as e:
            print(f"Test Failed: {e}")
            page.screenshot(path="/home/jules/verification/failure.png")
        finally:
            browser.close()
