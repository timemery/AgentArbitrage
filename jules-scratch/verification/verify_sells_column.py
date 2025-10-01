import re
import time
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Login
    page.goto("http://127.0.0.1:5000/")
    page.get_by_role("button", name="Log In").first.click()
    page.get_by_placeholder("Username").fill("tester")
    page.get_by_placeholder("Password").fill("OnceUponaBurgerTree-12monkeys")
    login_form = page.locator("form.login-form")
    login_form.get_by_role("button", name="Log In").click()
    expect(page).to_have_url(re.compile(".*guided_learning"), timeout=10000)

    # 2. Navigate to Data Sourcing and start a scan
    page.goto("http://127.0.0.1:5000/data_sourcing")
    page.get_by_placeholder("Enter number of deals").fill("5")
    page.get_by_role("button", name="Start New Scan").click()

    # 3. Poll for scan completion
    print("Waiting for data scan to complete...")
    for _ in range(60):  # Poll for up to 5 minutes (60 * 5s)
        try:
            response = page.request.get("http://127.0.0.1:5000/scan-status")
            status = response.json()
            print(f"Current scan status: {status.get('status')}")
            if status.get('status') == 'Completed':
                print("Scan completed successfully.")
                break
            elif status.get('status') == 'Failed':
                raise Exception("Scan failed. Check server logs.")
        except Exception as e:
            print(f"Error polling status: {e}")
        time.sleep(5)
    else:
        raise Exception("Timeout waiting for scan to complete.")

    # 4. Navigate to the dashboard and take screenshot
    page.goto("http://127.0.0.1:5000/dashboard")

    # 5. Wait for the headers to ensure the table is rendered
    sells_period_header = page.get_by_role("cell", name=re.compile("Sells Period", re.IGNORECASE))
    expect(sells_period_header).to_be_visible(timeout=15000)

    season_header = page.get_by_role("cell", name=re.compile("Season", re.IGNORECASE))
    expect(season_header).to_be_visible()

    # 6. Take the final screenshot
    page.screenshot(path="jules-scratch/verification/dashboard_verification.png")
    print("Screenshot saved to jules-scratch/verification/dashboard_verification.png")

    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)