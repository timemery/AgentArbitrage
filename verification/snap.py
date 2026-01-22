from playwright.sync_api import sync_playwright

def snap():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1600, "height": 1200})

        try:
            page.goto("http://localhost:5000/", timeout=30000)
            if page.is_visible("button.login-button"):
                page.click("button.login-button")
            page.fill("input[name='username']", "tester")
            page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

            if "/dashboard" not in page.url:
                page.goto("http://localhost:5000/dashboard")

            page.screenshot(path="verification/dashboard_fix.png")
            print("Snapshot taken.")
        except Exception as e:
            print(f"Error: {e}")
        browser.close()

if __name__ == "__main__":
    snap()
