from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Intercept API call to return mock data
    page.route("**/api/deals*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body="""{
            "deals": [
                {
                    "ASIN": "1234567890",
                    "Title": "Test Deal 1 - High Rank, New Condition",
                    "Condition": "New",
                    "Sales_Rank_Current": 4500000,
                    "Sales_Rank_365_days_avg": 4400000,
                    "last_price_change": "2023-01-01 12:00:00",
                    "Trend": "↘",
                    "Drops": 10,
                    "Offers": "12 ↘",
                    "Profit": 10.00,
                    "Margin": 50.00,
                    "AMZ": "⚠️",
                    "List_at": 20.00,
                    "Price_Now": 10.00,
                    "1yr_Avg": 15.00
                },
                {
                    "ASIN": "0987654321",
                    "Title": "Test Deal 2 - Mid Rank, Used-Like New",
                    "Condition": "Used - Like New",
                    "Sales_Rank_Current": 120000,
                    "Sales_Rank_365_days_avg": 115000,
                    "last_price_change": "2025-10-27 10:00:00",
                    "Trend": "↗",
                    "Drops": 5,
                    "Offers": "5 ↗",
                    "Profit": 5.00,
                    "Margin": 20.00,
                    "AMZ": "",
                    "List_at": 10.00,
                    "Price_Now": 5.00,
                    "1yr_Avg": 8.00
                },
                {
                    "ASIN": "1122334455",
                    "Title": "Test Deal 3 - Low Rank, Collectible",
                    "Condition": "Collectible - Very Good",
                    "Sales_Rank_Current": 500,
                    "Sales_Rank_365_days_avg": 600,
                    "last_price_change": "2025-10-27 13:55:00",
                    "Trend": "",
                    "Drops": 0,
                    "Offers": "1",
                    "Profit": 15.00,
                    "Margin": 30.00,
                    "AMZ": "",
                    "List_at": 30.00,
                    "Price_Now": 15.00,
                    "1yr_Avg": 20.00
                },
                {
                    "ASIN": "6677889900",
                    "Title": "Test Deal 4 - Malformed Condition",
                    "Condition": "used-good",
                    "Sales_Rank_Current": 999,
                    "Sales_Rank_365_days_avg": 1000,
                    "last_price_change": "2025-10-23 12:00:00",
                    "Trend": "⇨",
                    "Drops": 2,
                    "Offers": "3",
                    "Profit": 2.00,
                    "Margin": 10.00,
                    "AMZ": "",
                    "List_at": 12.00,
                    "Price_Now": 10.00,
                    "1yr_Avg": 11.00
                }
            ],
            "pagination": {
                "current_page": 1,
                "total_pages": 1,
                "total_records": 4
            }
        }"""
    ))

    # Mock deal-count
    page.route("**/api/deal-count*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"count": 4}'
    ))

    # Mock recalc-status
    page.route("**/api/recalc-status*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"status": "Idle"}'
    ))

    # Mock janitor
    page.route("**/api/run-janitor*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"status": "success"}'
    ))

    # Set fixed date
    page.add_init_script("""
        const OriginalDate = Date;
        class MockDate extends Date {
            constructor(...args) {
                if (args.length) {
                    super(...args);
                } else {
                    super("2025-10-27T14:00:00"); // Fixed "Now"
                }
            }
            static now() {
                return new MockDate().getTime();
            }
        }
        window.Date = MockDate;
    """)

    try:
        # 1. Login
        print("Navigating to login page...")
        page.goto("http://localhost:5000/")

        if "dashboard" not in page.url:
            print("Logging in...")
            # Toggle login form
            # Based on memory, there is a toggleable container.
            # We will try to click the first button that says "Log In" (case insensitive)
            page.click("button:has-text('Log In')")

            # Fill credentials
            page.fill("input[name='username']", "tester")
            page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")

            # Click submit. It might be the second "Log In" button or a specific submit button.
            # Assuming the form has a submit button.
            page.click("button[type='submit']")

            # Wait for navigation to /guided_learning or /dashboard
            print("Waiting for login redirect...")
            page.wait_for_url("**/guided_learning")
            print("Login successful.")

        # 2. Go to Dashboard
        print("Navigating to dashboard...")
        page.goto("http://localhost:5000/dashboard")

        # Wait for table to load
        page.wait_for_selector("#deals-table table")

        # Take screenshot
        page.screenshot(path="verification_dashboard.png", full_page=True)
        print("Screenshot saved to verification_dashboard.png")

    except Exception as e:
        print(f"Error: {e}")
        try:
            page.screenshot(path="error_state.png")
            print("Saved error_state.png")
        except:
            pass
    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
