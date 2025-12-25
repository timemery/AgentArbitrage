
import sqlite3
import os
import sys
from flask import Flask
from wsgi_handler import app, api_deals
import json

# Define DB path (adjust if necessary)
DB_PATH = "deals.db"
if not os.path.exists(DB_PATH):
    if os.path.exists("data/deals.db"):
        DB_PATH = "data/deals.db"
    elif os.path.exists("../deals.db"):
        DB_PATH = "../deals.db"

print(f"Using Database: {DB_PATH}")

def count_db_rows():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM deals")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"Error counting DB rows: {e}")
        return -1

def verify_api_counts():
    print("--- Verifying API vs DB Counts ---")

    # 1. Get Raw DB Count
    db_count = count_db_rows()
    print(f"Raw DB Count: {db_count}")

    # 2. Simulate API Call
    # We need to set the DATABASE_URL env var or ensure the app uses the correct one
    # The app code uses: DATABASE_URL = os.getenv("DATABASE_URL", ...)
    # Let's set it explicitly for the test context
    os.environ["DATABASE_URL"] = DB_PATH

    with app.test_request_context('/api/deals?limit=10000'): # High limit to get all
        # Mock session if needed, though api_deals doesn't strictly require login
        # for basic deal fetching (it does for restrictions, but we just want the count)
        # Looking at code: check logic for session usage.
        # It uses session.get('sp_api_connected') but doesn't block if not logged in?
        # WAIT: wsgi_handler.py doesn't have @login_required on api_deals,
        # but the function body doesn't check 'logged_in' explicitly at the start?
        # Let's check the code again.
        # ...
        # The route definition: @app.route('/api/deals')
        # Function body:
        # is_sp_api_connected = session.get('sp_api_connected', False)
        # user_id = session.get('sp_api_user_id')
        # ...
        # It does NOT verify login at the top. So we should be good.

        try:
            response = api_deals()
            # response is a Flask Response object, or jsonify return
            # jsonify returns a Response object with .get_json() or .data

            if hasattr(response, 'get_json'):
                data = response.get_json()
            else:
                # If it's a raw response (unlikely with jsonify)
                data = json.loads(response.data)

            api_total_records = data['pagination']['total_records']
            api_total_db_records = data['pagination']['total_db_records']
            api_returned_count = len(data['deals'])

            print(f"API Total Records (Filtered): {api_total_records}")
            print(f"API Total DB Records (Unfiltered): {api_total_db_records}")
            print(f"API Returned Items in Response: {api_returned_count}")

            if db_count != api_total_db_records:
                print("MISMATCH: Raw DB count != API reported total_db_records")
            else:
                print("MATCH: Raw DB count == API reported total_db_records")

            if api_total_records < db_count:
                print("Warning: API is applying filters (total_records < total_db_records)")

        except Exception as e:
            print(f"Error calling API: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    verify_api_counts()
