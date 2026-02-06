from playwright.sync_api import sync_playwright, expect
import time

def verify_responsive(page):
    # Login
    page.goto("http://localhost:5000/")

    # Check if we are at login
    if "Log In" in page.content() or page.locator("input[name='username']").is_visible():
        print("Logging in...")
        # If login form is hidden (it is by default in index.html, click Log In button first?)
        # CSS: .login-form { display: none; } .show-form .login-form { display: flex; }
        # Button: <button class="login-button" onclick="document.body.classList.toggle('show-form')">Log In</button>

        login_btn = page.locator("button.login-button")
        if login_btn.is_visible():
            login_btn.click()

        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard")
        print("Logged in.")
    else:
        print("Already logged in or on dashboard.")

    page.goto("http://localhost:5000/dashboard")
    page.wait_for_load_state("networkidle")
    # Wait for table to load
    page.wait_for_selector("#deals-table table", timeout=10000)

    # 1. Viewport 1200px (Max Width Check)
    print("Checking 1200px...")
    page.set_viewport_size({"width": 1200, "height": 800})
    time.sleep(1) # Wait for resize
    page.screenshot(path="verification/dashboard_1200.png")

    # 2. Viewport 1100px (Filter Panel Check)
    print("Checking 1100px (Filter Panel wrap)...")
    page.set_viewport_size({"width": 1100, "height": 800})
    time.sleep(1)
    page.screenshot(path="verification/dashboard_1100.png")

    # 3. Viewport 900px (Navbar Breakpoint)
    print("Checking 900px (Navbar resize)...")
    page.set_viewport_size({"width": 900, "height": 800})
    time.sleep(1)
    page.screenshot(path="verification/dashboard_900.png")

    # 4. Viewport 700px (Navbar Clipping & Column hiding)
    print("Checking 700px (Navbar clipping & hidden cols)...")
    page.set_viewport_size({"width": 700, "height": 800})
    time.sleep(1)
    page.screenshot(path="verification/dashboard_700.png")

    # 5. Viewport 375px (Mobile View)
    print("Checking 375px (Mobile View)...")
    page.set_viewport_size({"width": 375, "height": 800})
    time.sleep(1)
    page.screenshot(path="verification/dashboard_375.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_responsive(page)
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error_state.png")
        finally:
            browser.close()
