
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

    # Set DATABASE_URL for the app
    os.environ["DATABASE_URL"] = DB_PATH

    # 2. Simulate API Call (Unfiltered)
    print("\n[TEST 1] Unfiltered API Call (/api/deals)")
    with app.test_request_context('/api/deals?limit=10000'):
        try:
            response = api_deals()
            if hasattr(response, 'get_json'):
                data = response.get_json()
            else:
                data = json.loads(response.data)

            api_total_db_records = data['pagination']['total_db_records']
            api_returned_count = len(data['deals'])

            print(f"API Total DB Records: {api_total_db_records}")
            print(f"API Returned Items: {api_returned_count}")

            if db_count == api_total_db_records:
                 print("Result: MATCH (DB Count matches API Unfiltered Count)")
            else:
                 print("Result: MISMATCH")

        except Exception as e:
            print(f"Error calling API: {e}")

    # 3. Simulate API Call (Default Dashboard Filter)
    print("\n[TEST 2] Default Dashboard Filter (/api/deals?margin_gte=0)")
    with app.test_request_context('/api/deals?limit=10000&margin_gte=0'):
        try:
            response = api_deals()
            if hasattr(response, 'get_json'):
                data = response.get_json()
            else:
                data = json.loads(response.data)

            filtered_count = data['pagination']['total_records']

            print(f"Dashboard Visible Deals (Margin >= 0%): {filtered_count}")
            print(f"Hidden Deals (Negative Margin or NULL): {db_count - filtered_count}")

            if filtered_count < db_count:
                print("Note: The Dashboard applies a default filter of Margin >= 0%.")
                print("      Deals with negative margins or missing data are hidden by default.")

        except Exception as e:
             print(f"Error calling API: {e}")

if __name__ == "__main__":
    verify_api_counts()
