
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to the login page
    page.goto("http://127.0.0.1:5000/")

    # Click the login button to reveal the form
    page.locator('button[onclick="toggleForm()"]').click()

    # Fill in the login form
    page.get_by_placeholder("Username").fill("tester")
    page.get_by_placeholder("Password").fill("OnceUponaBurgerTree-12monkeys")

    # Submit the form
    page.locator('#login-form button:has-text("Login")').click()
    page.wait_for_load_state("networkidle")


    # Go to the settings page
    page.goto("http://127.0.0.1:5000/settings")

    # Set up a listener for the confirmation dialog
    page.on("dialog", lambda dialog: dialog.accept())

    # Click the "Refresh All Data" button
    page.get_by_role("button", name="Refresh All Data").click()

    # Take a screenshot
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
