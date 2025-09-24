from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("http://localhost:5000/")

    # Click the login button to reveal the form
    page.click("button.login-button")

    # Wait for the form to be visible
    page.wait_for_selector("form.login-form")

    # Log in
    page.get_by_placeholder("Username").fill("tester")
    page.get_by_placeholder("Password").fill("OnceUponaBurgerTree-12monkeys")
    page.locator("form.login-form button[type='submit']").click()

    # Wait for navigation to the guided learning page and then go to the dashboard
    expect(page).to_have_url("http://localhost:5000/guided_learning")
    page.get_by_role("link", name="Dashboard").click()
    expect(page).to_have_url("http://localhost:5000/dashboard")

    # Take a screenshot of the dashboard
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)