from playwright.sync_api import sync_playwright, expect
import os
import sqlite3
import time

def setup_db():
    """Ensure the database has some dummy data to display."""
    conn = sqlite3.connect('deals.db')
    cursor = conn.cursor()
    # Create tables if they don't exist (simplified schema)
    cursor.execute('''CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY,
        ASIN TEXT,
        Title TEXT,
        Condition TEXT,
        Binding TEXT,
        Sales_Rank_Current INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_credentials (
        user_id TEXT PRIMARY KEY,
        refresh_token TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_restrictions (
        asin TEXT,
        user_id TEXT,
        is_restricted INTEGER,
        approval_url TEXT
    )''')

    # Insert test data with various bindings
    cursor.execute("DELETE FROM deals") # Clear existing
    deals = [
        ('B000001', 'Test Book 1', 'Used - Good', 'library_binding', 50000),
        ('B000002', 'Test Book 2', 'Used - Very Good', 'mass-market', 150000),
        ('B000003', 'Test Book 3', 'New', 'sheet_music', 1000),
        ('B000004', 'Test Book 4', 'Used - Acceptable', 'audio_cd', 25000),
        ('B000005', 'Test Book 5', 'New', 'hardcover', 500),
    ]
    cursor.executemany("INSERT INTO deals (ASIN, Title, Condition, Binding, Sales_Rank_Current) VALUES (?, ?, ?, ?, ?)", deals)
    conn.commit()
    conn.close()

def verify_binding_display(page):
    # Log in
    page.goto("http://localhost:5000/")

    # Click the toggle button to show the form first
    page.click('button.login-button')

    page.fill('input[name="username"]', 'AristotleLogic')
    page.fill('input[name="password"]', 'virtueLiesInGoldenMean')
    page.click('button[type="submit"]')

    # Wait for dashboard
    print(f"Page title after login: {page.title()}")

    # Increase timeout and take debug screenshot if it fails
    try:
        page.wait_for_selector('#deals-table', state='attached', timeout=20000)
    except Exception as e:
        page.screenshot(path="verification/debug_fail.png", full_page=True)
        print(f"Failed to find table. Screenshot saved to verification/debug_fail.png")
        raise e

    # Take screenshot of the table
    page.screenshot(path="verification/dashboard_view.png", full_page=True)

    # Check for specific bindings
    deals_table = page.locator('#deals-table')
    deals_table.screenshot(path="verification/binding_column_verification.png")

if __name__ == "__main__":
    setup_db()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_binding_display(page)
            print("Verification script ran successfully.")
        except Exception as e:
            print(f"Verification failed: {e}")
        finally:
            browser.close()
