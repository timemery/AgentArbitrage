from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the login page
        page.goto("http://127.0.0.1:5000/")

        # Click the login button to reveal the form
        page.get_by_role("button", name="Log In").click()

        # Fill in the credentials
        page.get_by_placeholder("Username").fill("tester")
        page.get_by_placeholder("Password").fill("OnceUponaBurgerTree-12monkeys")

        # Use a more specific selector for the submission button inside the form
        page.locator("form.login-form button[type='submit']").click()

        # Navigate to the settings page
        page.goto("http://127.0.0.1:5000/settings")

        # Click the 'Edit' button to enable the form fields
        edit_button = page.get_by_role("button", name="Edit")
        expect(edit_button).to_be_visible()
        edit_button.click()

        # Expect the new fields to be visible and enabled
        expect(page.get_by_label("Max Sales Rank")).to_be_visible()
        expect(page.get_by_label("Max Sales Rank")).to_be_enabled()

        expect(page.get_by_label("Min Price")).to_be_visible()
        expect(page.get_by_label("Min Price")).to_be_enabled()

        # Take a screenshot to verify the new fields are present
        screenshot_path = "jules-scratch/verification/settings_page_verification.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    run_verification()