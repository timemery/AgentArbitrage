
import sys
import os
from playwright.sync_api import sync_playwright, expect

def verify_dark_mode():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to login
        print("Navigating to login page...")
        page.goto("http://localhost:5000/")

        # Click login button to show form
        page.click(".login-button")

        # Check input styles
        print("Checking input styles...")
        username_input = page.locator("input[name='username']")

        # Get computed styles
        bg_color = username_input.evaluate("el => getComputedStyle(el).backgroundColor")
        color = username_input.evaluate("el => getComputedStyle(el).color")

        print(f"Input Background: {bg_color}")
        print(f"Input Color: {color}")

        # Check if background is dark (rgba(0, 0, 0, 0.2) or close to it)
        # Playwright might return rgba(0, 0, 0, 0.2) as string
        if "rgba(0, 0, 0, 0.2)" not in bg_color:
             print("WARNING: Background color might not be correct.")

        # Check if text is white
        if "rgb(255, 255, 255)" not in color and "white" not in color:
             print("WARNING: Text color might not be white.")

        # Take screenshot
        if not os.path.exists("verification"):
            os.makedirs("verification")
        page.screenshot(path="verification/login_dark_mode.png")
        print("Screenshot saved to verification/login_dark_mode.png")

        browser.close()

if __name__ == "__main__":
    try:
        verify_dark_mode()
    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(1)
