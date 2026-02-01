from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Log in
    page.goto("http://localhost:5000")

    # Click Log In button to show form
    page.click("button.login-button")
    page.wait_for_selector("form.login-form", state="visible")

    page.fill('input[name="username"]', "tester")
    page.fill('input[name="password"]', "OnceUponaBurgerTree-12monkeys")

    # Click Submit button explicitly
    page.click("form.login-form button[type='submit']")

    # Go to Dashboard
    page.wait_for_url("**/dashboard")
    page.wait_for_selector("#filter-panel")

    # Check if panel is open
    if page.locator("#panel-open").is_hidden():
        page.click("#filter-icon-closed")
        page.wait_for_selector("#panel-open", state="visible")

    # Check Profit Slider Label
    profit_label = page.locator("label[for='profit_slider'] span")
    expect(profit_label).to_have_text("Any")
    print("Profit Label verified: Any")

    # Check Margin Slider Label
    margin_label = page.locator("label[for='min_profit_margin_slider'] span")
    expect(margin_label).to_have_text("Any")
    print("Margin Label verified: Any")

    # Take screenshot
    page.screenshot(path="verification/dashboard_filters.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
