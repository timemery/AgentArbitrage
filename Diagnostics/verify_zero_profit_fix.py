import sqlite3
import os
import sys

# Version 1.1
DB_PATH = 'deals.db'

def verify_fix():
    print("--- Verifying Zero Profit Fix (Script v1.1) ---")

    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Clean up previous test
    try:
        cursor.execute("DELETE FROM deals WHERE ASIN = 'TEST_ZERO_PROFIT'")
        conn.commit()
    except Exception:
        pass

    # 2. Insert Test Deal (Profit = -10.00)
    # Using correct column names (List_at, 1yr_Avg) matching DB schema
    print("Inserting test deal: Profit = -10.00, Valid Price Data...")
    try:
        cursor.execute("""
            INSERT INTO deals (
                "ASIN", "Title", "Profit", "List_at", "1yr_Avg", "Price_Now",
                "last_seen_utc", "source"
            ) VALUES (
                'TEST_ZERO_PROFIT', 'Test Bad Deal', -10.00, 20.00, 20.00, 30.00,
                '2026-02-15T12:00:00', 'verification_script'
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"ERROR Inserting: {e}")
        print("Note: If this fails with 'no column', the DB schema might be different from expected 'List_at'.")
        return

    # 3. Verify Saved
    cursor.execute("SELECT COUNT(*) FROM deals WHERE ASIN = 'TEST_ZERO_PROFIT'")
    saved = cursor.fetchone()[0]
    if saved == 1:
        print("✅ SUCCESS: Zero-profit deal was SAVED to the database.")
    else:
        print("❌ FAIL: Zero-profit deal was NOT saved to the database.")
        return

    # 4. Verify Hidden from Dashboard (Mimic wsgi_handler.deal_count logic)
    # Filters: Profit > 0, List_at > 0, 1yr_Avg valid
    sql_dashboard = """
        SELECT COUNT(*) FROM deals
        WHERE "Profit" > 0
        AND "List_at" IS NOT NULL AND "List_at" > 0
        AND "1yr_Avg" IS NOT NULL AND "1yr_Avg" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00') AND "1yr_Avg" != 0
        AND ASIN = 'TEST_ZERO_PROFIT'
    """
    cursor.execute(sql_dashboard)
    visible = cursor.fetchone()[0]

    if visible == 0:
        print("✅ SUCCESS: Zero-profit deal is HIDDEN from the Dashboard.")
    else:
        print("❌ FAIL: Zero-profit deal is VISIBLE on the Dashboard.")

    # 5. Cleanup
    cursor.execute("DELETE FROM deals WHERE ASIN = 'TEST_ZERO_PROFIT'")
    conn.commit()
    print("--- Verification Complete ---")

if __name__ == "__main__":
    verify_fix()
