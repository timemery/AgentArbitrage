
import sqlite3
import os
import sys
import json

# Ensure we can import modules from the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from flask import Flask
from wsgi_handler import app, api_deals

# Define DB path
# We are in Diagnostics/, so ../deals.db or ../data/deals.db
DB_PATH = os.path.join(root_dir, "deals.db")
if not os.path.exists(DB_PATH):
    if os.path.exists(os.path.join(root_dir, "data/deals.db")):
        DB_PATH = os.path.join(root_dir, "data/deals.db")

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

    with app.test_request_context('/api/deals?limit=10000'):
        try:
            response = api_deals()

            if hasattr(response, 'get_json'):
                data = response.get_json()
            else:
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
