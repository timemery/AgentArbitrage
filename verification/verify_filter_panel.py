import os
import time
from playwright.sync_api import sync_playwright

def verify_filter_panel():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print("Navigating to login page...")
        try:
            page.goto("http://localhost:5000/")
            # Login
            if page.locator("button.login-button").is_visible():
                page.click("button.login-button")
                time.sleep(0.5)

            page.fill("input[name='username']", "tester")
            page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
            page.click("form.login-form button[type='submit']")
            page.wait_for_url("**/dashboard", timeout=10000)
            print("Login successful, dashboard loaded.")
        except Exception as e:
            print(f"Login failed: {e}")
            if "/dashboard" not in page.url:
                return

        try:
            page.wait_for_selector(".filter-bar", timeout=10000)
        except:
             print("Timeout waiting for .filter-bar.")
             return

        # Check Initial State
        dropdown = page.locator(".filter-dropdown")
        buttons = page.locator(".panel-right-buttons")

        # Ensure open
        if not dropdown.is_visible():
            page.click("#filter-icon-toggle")
            page.wait_for_timeout(1000)

        # Verify Open State
        is_visible = dropdown.is_visible()
        print(f"Dropdown visible: {is_visible}")

        # Check background color
        filter_bar = page.locator(".filter-bar")
        bg_color = filter_bar.evaluate("el => getComputedStyle(el).backgroundColor")
        if "rgb(19, 29, 57)" in bg_color or "#131d39" in bg_color:
             print("Filter Bar Background Color CORRECT")
        else:
             print(f"Filter Bar Background Color INCORRECT: {bg_color}")

        # Check Separator Line
        separator_bg = dropdown.evaluate("el => getComputedStyle(el, '::before').backgroundColor")
        if "rgb(42, 59, 76)" in separator_bg or "#2a3b4c" in separator_bg:
                print("Separator Color CORRECT")
        else:
                print(f"Separator Color INCORRECT: {separator_bg}")

        # Check Button Alignment
        dropdown_box = dropdown.bounding_box()
        buttons_box = buttons.bounding_box()

        if buttons_box and dropdown_box:
            midpoint = dropdown_box['x'] + dropdown_box['width'] / 2
            if buttons_box['x'] > midpoint:
                print("Buttons are on the RIGHT side.")
            else:
                print("Buttons are on the LEFT side.")

        # Screenshot Open
        page.screenshot(path="verification/filter_panel_final.png")

        browser.close()

if __name__ == "__main__":
    verify_filter_panel()
