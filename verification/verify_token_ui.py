
import subprocess
import time
import os
import signal
from playwright.sync_api import sync_playwright

def verify_token_error_feedback():
    # Start Flask app
    # Use environment variables for DB path if needed, but relative path should work
    flask_proc = subprocess.Popen(['python3', 'wsgi_handler.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # 1. Login
            page.goto("http://127.0.0.1:5000/login")

            # Check if login is required
            if page.locator("input[name='username']").count() > 0:
                print("Logging in...")
                page.fill("input[name='username']", "tester")
                page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
                page.click("button[type='submit']")
                page.wait_for_url("**/dashboard")
                print("Logged in.")
            elif page.get_by_text("Log In").count() > 0:
                 print("Clicking 'Log In' button to reveal form...")
                 page.get_by_text("Log In").click()
                 page.fill("input[name='username']", "tester")
                 page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
                 page.click("button[type='submit']")
                 page.wait_for_url("**/dashboard")
                 print("Logged in.")
            else:
                print("Already logged in.")

            # 2. Go to Settings
            page.goto("http://127.0.0.1:5000/settings")

            # 3. Check for Connected State OR Alternative Manual Connection Form

            # If "Connected!" header is present, we test the Manual Update Form
            if page.locator("h5:has-text('Connected!')").count() > 0:
                print("App is in 'Connected' state. Testing Manual Update Form.")

                # Check for the Toggle Button
                toggle_btn = page.locator("button:has-text('Toggle Manual Update Form')")
                if toggle_btn.count() > 0:
                    print("Found Toggle Button. Clicking...")
                    toggle_btn.click()

                    # Wait for form visibility
                    page.wait_for_selector("#manualUpdateForm", state="visible")

                    # Fill Form
                    page.fill("#update_seller_id", "TEST_SELLER_ID")
                    page.fill("#update_refresh_token", "Atzr|TestToken123")
                    page.click("button:has-text('Update Credentials')")

                    # Verify Success Message
                    page.wait_for_selector(".alert-success-custom", timeout=5000)
                    success_msg = page.locator(".alert-success-custom").text_content()

                    if "Successfully connected manually!" in success_msg:
                        print("Manual Update Form submission successful.")
                        page.screenshot(path="verification/verification_token_ui_connected.png")
                        return True
                    else:
                        print(f"Unexpected feedback: {success_msg}")
                        return False
                else:
                    print("Toggle Button not found in Connected state.")
                    return False

            # If not connected, check for the disconnected state Manual Connection Form
            elif page.locator("h6:has-text('Alternative: Manual Connection')").count() > 0:
                print("App is in 'Disconnected' state. Testing Manual Connection Form.")

                # Fill Form
                page.fill("#manual_seller_id", "TEST_SELLER_ID")
                page.fill("#manual_refresh_token", "Atzr|TestToken123")
                page.click("button:has-text('Connect Manually')")

                # Verify Success Message
                page.wait_for_selector(".alert-success-custom", timeout=5000)
                success_msg = page.locator(".alert-success-custom").text_content()

                if "Successfully connected manually!" in success_msg:
                    print("Manual Connection Form submission successful.")
                    page.screenshot(path="verification/verification_token_ui_disconnected.png")
                    return True
                else:
                    print(f"Unexpected feedback: {success_msg}")
                    return False

            else:
                print("Neither Connected state nor Alternative Manual Connection form found.")
                # Log page content for debugging
                with open("verification/debug_settings.html", "w") as f:
                    f.write(page.content())
                return False

    except Exception as e:
        print(f"Verification Failed: {e}")
        return False
    finally:
        os.kill(flask_proc.pid, signal.SIGTERM)

if __name__ == "__main__":
    if verify_token_error_feedback():
        print("Verification SUCCESS!")
    else:
        print("Verification FAILED.")
