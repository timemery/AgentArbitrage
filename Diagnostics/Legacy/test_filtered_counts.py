
import sqlite3
import os
import sys
import json
from flask import session

# Ensure we can import modules from the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from flask import Flask
from wsgi_handler import app, deal_count

# Define DB path
DB_PATH = os.path.join(root_dir, "deals.db")
if not os.path.exists(DB_PATH):
    if os.path.exists(os.path.join(root_dir, "data/deals.db")):
        DB_PATH = os.path.join(root_dir, "data/deals.db")

print(f"Using Database: {DB_PATH}")

def test_filtered_counts():
    print("--- Testing Filtered Deal Counts ---")

    os.environ["DATABASE_URL"] = DB_PATH

    # 1. Test Unfiltered
    with app.test_request_context('/api/deal-count'):
        session['logged_in'] = True # Mock login
        try:
            response = deal_count()
            if hasattr(response, 'get_json'):
                data = response.get_json()
            else:
                data = json.loads(response.data)
            print(f"Unfiltered Count: {data.get('count')}")
        except Exception as e:
            print(f"Error testing unfiltered: {e}")

    # 2. Test Filtered
    with app.test_request_context('/api/deal-count?margin_gte=10000'):
        session['logged_in'] = True # Mock login
        try:
            response = deal_count()
            if hasattr(response, 'get_json'):
                data = response.get_json()
            else:
                data = json.loads(response.data)
            print(f"Filtered Count (Margin >= 10000%): {data.get('count')}")

            if data.get('count') == 0:
                print("SUCCESS: Filter correctly returned 0.")
            else:
                print(f"WARNING: Filter returned {data.get('count')}. DB might contain high margin items.")
        except Exception as e:
            print(f"Error testing filtered: {e}")

if __name__ == "__main__":
    test_filtered_counts()
