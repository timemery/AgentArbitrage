import os
import sys
import sqlite3
import json
import logging
from unittest.mock import patch

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DATABASE_URL to a test DB
TEST_DB = 'test_reproduce.db'
os.environ['DATABASE_URL'] = TEST_DB

from wsgi_handler import app
from keepa_deals.db_utils import create_deals_table_if_not_exists, create_user_restrictions_table_if_not_exists

def setup_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    # Initialize tables
    create_deals_table_if_not_exists()
    create_user_restrictions_table_if_not_exists()

    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()

    # Insert test deals
    deals = [
        ("ASIN1", "Book 1", 1000, 20.0), # Restricted
        ("ASIN2", "Book 2", 2000, 30.0), # Not Restricted
        ("ASIN3", "Book 3", 3000, 40.0), # Error (-1)
        ("ASIN4", "Book 4", 4000, 50.0), # Pending (No entry)
    ]

    for asin, title, rank, price in deals:
        cursor.execute(
            'INSERT INTO deals (ASIN, Title, "Sales_Rank_Current", "Price_Now") VALUES (?, ?, ?, ?)',
            (asin, title, rank, price)
        )

    # Insert test restrictions
    # user_id 'test_user'
    # 1 = Restricted, 0 = Not Restricted, -1 = Error
    cursor.execute('INSERT INTO user_restrictions (user_id, asin, is_restricted, approval_url) VALUES (?, ?, ?, ?)',
                   ('test_user', 'ASIN1', 1, 'http://apply.url'))
    cursor.execute('INSERT INTO user_restrictions (user_id, asin, is_restricted, approval_url) VALUES (?, ?, ?, ?)',
                   ('test_user', 'ASIN2', 0, None))
    cursor.execute('INSERT INTO user_restrictions (user_id, asin, is_restricted, approval_url) VALUES (?, ?, ?, ?)',
                   ('test_user', 'ASIN3', -1, 'ERROR'))

    conn.commit()
    conn.close()

def test_api_deals():
    setup_db()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'tester'
            sess['sp_api_connected'] = True
            sess['sp_api_user_id'] = 'test_user'

        response = client.get('/api/deals')
        data = json.loads(response.data)

        # print(json.dumps(data, indent=2))

        deals = {d['ASIN']: d for d in data['deals']}

        # Check ASIN1 (Restricted)
        if deals['ASIN1'].get('restriction_status') != 'restricted':
            print("FAIL: ASIN1 should be restricted")
        else:
            print("PASS: ASIN1 is restricted")

        # Check ASIN2 (Not Restricted)
        if deals['ASIN2'].get('restriction_status') != 'not_restricted':
            print("FAIL: ASIN2 should be not_restricted")
        else:
            print("PASS: ASIN2 is not_restricted")

        # Check ASIN3 (Error) - This is the bug we want to verify
        status3 = deals['ASIN3'].get('restriction_status')
        print(f"ASIN3 status: {status3}")
        if status3 == 'error':
            print("PASS: ASIN3 is error (Fixed)")
        else:
            print(f"FAIL: ASIN3 should be error but is {status3} (Reproduced Bug)")

        # Check ASIN4 (Pending)
        if deals['ASIN4'].get('restriction_status') != 'pending_check':
            print("FAIL: ASIN4 should be pending_check")
        else:
            print("PASS: ASIN4 is pending_check")

if __name__ == '__main__':
    test_api_deals()
