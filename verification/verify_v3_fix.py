from playwright.sync_api import sync_playwright

def verify_v3_fix():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1600, "height": 1200})

        print("Navigating...")
        try:
            page.goto("http://localhost:5000/", timeout=30000)
        except Exception as e:
            print(f"Navigation failed: {e}")
            return

        print("Logging in...")
        if page.is_visible("button.login-button"):
            page.click("button.login-button")

        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        print("Going to dashboard...")
        if "/dashboard" not in page.url:
            page.goto("http://localhost:5000/dashboard")

        print("Waiting for table...")
        try:
            page.wait_for_selector(".deal-row", timeout=10000)
        except:
            print("Table timeout. Continuing check anyway.")

        # Check Border Spacing
        bs = page.eval_on_selector("#deals-table table", "el => window.getComputedStyle(el).borderSpacing")
        print(f"Border Spacing: {bs}")

        # Check Filter Panel
        bg = page.eval_on_selector(".filter-panel", "el => window.getComputedStyle(el).backgroundColor")
        print(f"Filter BG: {bg}")

        # Check Offsets
        g_top = page.eval_on_selector(".group-header th", "el => window.getComputedStyle(el).top")
        c_top = page.eval_on_selector(".column-header-row th", "el => window.getComputedStyle(el).top")
        s_top = page.eval_on_selector(".sort-arrows-row td", "el => window.getComputedStyle(el).top")
        print(f"Offsets: {g_top}, {c_top}, {s_top}")

        # Check Spacer Rows
        count = page.locator(".spacer-row").count()
        print(f"Spacer Rows: {count}")

        browser.close()

if __name__ == "__main__":
    verify_v3_fix()
