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
            # Login if needed
            if page.locator("button.login-button").is_visible():
                page.click("button.login-button")
                time.sleep(0.5)
                page.fill("input[name='username']", "tester")
                page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
                page.click("form.login-form button[type='submit']")
                page.wait_for_url("**/dashboard", timeout=10000)
            elif "/dashboard" not in page.url:
                 # Already logged in maybe? Or failed.
                 pass
        except Exception as e:
            print(f"Login process check: {e}")

        if "/dashboard" not in page.url:
             print("Not on dashboard. Exiting.")
             return

        try:
            page.wait_for_selector(".filter-bar", timeout=10000)
        except:
             print("Timeout waiting for .filter-bar.")
             return

        filter_bar = page.locator(".filter-bar")
        dropdown = page.locator(".filter-dropdown")

        # Ensure Open
        if not dropdown.is_visible():
            print("Panel Closed. Opening...")
            page.click("#filter-icon-toggle")
            page.wait_for_timeout(1000)

        # Verify Open State
        print(f"Dropdown visible: {dropdown.is_visible()}")

        # Check 'open' class
        classes = filter_bar.get_attribute("class")
        print(f"Filter Bar Classes: {classes}")
        if "open" in classes:
             print("Class 'open' PRESENT on filter-bar.")
        else:
             print("Class 'open' MISSING from filter-bar.")

        # Check background color
        bg_color = filter_bar.evaluate("el => getComputedStyle(el).backgroundColor")
        # #1f293c is rgb(31, 41, 60)
        print(f"Filter Bar Background Color: {bg_color}")
        if "rgb(31, 41, 60)" in bg_color or "#1f293c" in bg_color:
             print("Filter Bar Background Color CORRECT")
        else:
             print(f"Filter Bar Background Color INCORRECT: {bg_color}")

        # Check Border Radius (Bottom Left)
        radius = filter_bar.evaluate("el => getComputedStyle(el).borderBottomLeftRadius")
        print(f"Bottom Left Radius: {radius}")
        if radius == "0px":
             print("Bottom Left Radius CORRECT (0px)")
        else:
             print(f"Bottom Left Radius INCORRECT: {radius}")

        # Check Bottom Border
        border_bottom = filter_bar.evaluate("el => getComputedStyle(el).borderBottomWidth")
        print(f"Bottom Border Width: {border_bottom}")
        # It should be 0px if border-style is none, or width 0
        if border_bottom == "0px":
             print("Bottom Border Width CORRECT (0px)")
        else:
             # Sometimes computed style returns width even if style is none, so check style
             border_style = filter_bar.evaluate("el => getComputedStyle(el).borderBottomStyle")
             print(f"Bottom Border Style: {border_style}")
             if border_style == "none":
                 print("Bottom Border Style CORRECT (none)")
             else:
                 print("Bottom Border INCORRECT")

        # Screenshot Open
        page.screenshot(path="verification/filter_panel_refined.png")

        browser.close()

if __name__ == "__main__":
    verify_filter_panel()
