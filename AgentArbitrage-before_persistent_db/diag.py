# diag.py
import os
import sys
import json
import sqlite3
from dotenv import load_dotenv

# Add the project directory to the Python path to allow imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# It's critical to import our own modules after setting the path
from keepa_deals.keepa_api import fetch_deals_for_deals
from keepa_deals.db_utils import create_deals_table_if_not_exists

def run_diagnostic():
    print("--- STARTING DIAGNOSTIC SCRIPT ---")

    # 1. Load Environment
    print("\n[Step 1] Loading environment variables...")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("  [FAIL] KEEPA_API_KEY not found in .env file. Aborting.")
        return
    print(f"  [OK] KEEPA_API_KEY loaded.")

    # 2. API Call
    print("\n[Step 2] Calling Keepa API (fetch_deals_for_deals)...")
    try:
        # Using a 30-day range to maximize chances of finding deals
        deal_response = fetch_deals_for_deals(30, api_key, use_deal_settings=True)
        
        if deal_response is None:
            print("  [FAIL] API call returned None. This is the point of failure.")
            print("  Please check for any logged errors from keepa_api.py if possible.")
            return

        deals = deal_response.get('deals', {}).get('dr', [])
        print(f"  [OK] API call successful. Found {len(deals)} deals.")
        
        if not deals:
            print("  [INFO] The API call worked, but no deals matched the criteria in settings.json within the last 30 days.")

    except Exception as e:
        print(f"  [FAIL] An unexpected exception occurred during the API call: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Database Interaction
    print("\n[Step 3] Testing database connection and write access...")
    db_path = os.path.join(project_root, 'deals.db')
    print(f"  - Database path: {db_path}")
    if os.path.exists(db_path):
        print(f"  - DB file exists. Size: {os.path.getsize(db_path)} bytes.")
    else:
        print("  - DB file does not exist.")

    try:
        print("  - Ensuring table exists...")
        create_deals_table_if_not_exists()
        print("  - Table check/creation complete.")

        print("  - Connecting to database...")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            print("  - Connection successful.")
            
            print("  - Attempting to insert a test record...")
            test_asin = "DIAGNOSTIC_TEST"
            cursor.execute("DELETE FROM deals WHERE ASIN = ?", (test_asin,))
            cursor.execute("INSERT INTO deals (ASIN, Title) VALUES (?, ?)", (test_asin, "This is a diagnostic test record"))
            conn.commit()
            print("  - Test record inserted and committed successfully.")

            print("  - Verifying test record...")
            cursor.execute("SELECT Title FROM deals WHERE ASIN = ?", (test_asin,))
            result = cursor.fetchone()
            if result and result[0] == "This is a diagnostic test record":
                print("  [OK] Database write and read verified.")
            else:
                print("  [FAIL] Test record could not be verified after write.")

    except Exception as e:
        print(f"  [FAIL] An unexpected exception occurred during database interaction: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n--- DIAGNOSTIC SCRIPT FINISHED ---")

if __name__ == "__main__":
    run_diagnostic()