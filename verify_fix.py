import sqlite3
import os
import requests
import time
import subprocess
import signal

DB_PATH = 'migration_test.db'

def setup_db_without_drops():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Create simple table without Drops
    cursor.execute('CREATE TABLE deals (id INTEGER PRIMARY KEY, ASIN TEXT UNIQUE, Title TEXT, Condition TEXT, "Deal_Trust" REAL, "Seller_Quality_Score" REAL, "Sales_Rank_Current" INTEGER, "Profit" REAL, "All_in_Cost" REAL, "List_at" REAL, "1yr_Avg" TEXT, "AMZ" TEXT)')
    # Insert data
    cursor.execute('INSERT INTO deals (ASIN, Title, Condition, Sales_Rank_Current, Profit, All_in_Cost, List_at, "1yr_Avg") VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   ('B_NEW', 'New Item', '1', 50000, 10.0, 20.0, 40.0, '35.0'))
    cursor.execute('INSERT INTO deals (ASIN, Title, Condition, Sales_Rank_Current, Profit, All_in_Cost, List_at, "1yr_Avg") VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   ('B_USED', 'Used Item', '2', 50000, 10.0, 20.0, 40.0, '35.0'))
    conn.commit()
    conn.close()
    print("Database created without Drops column.")

def check_drops_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(deals)")
    cols = [row[1] for row in cursor.fetchall()]
    conn.close()
    if 'Sales_Rank_Drops_last_30_days' in cols:
        print("PASS: Sales_Rank_Drops_last_30_days found.")
        return True
    else:
        print(f"FAIL: Columns found: {cols}")
        return False

def test_api_logic():
    # Start server with this DB
    env = os.environ.copy()
    env['DATABASE_URL'] = DB_PATH

    print("Starting server to trigger migration...")
    proc = subprocess.Popen(['python3', 'wsgi_handler.py'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    time.sleep(5) # Wait for startup

    # Check if migration happened
    if check_drops_column():
        print("Migration verification successful.")
    else:
        print("Migration verification FAILED.")
        proc.terminate()
        return

    # Test API
    try:
        # Check all deals first
        print("Checking all deals...")
        r = requests.get('http://127.0.0.1:5000/api/deals')
        print(f"All Deals Status: {r.status_code}")
        data = r.json()
        count = len(data.get('deals', []))
        print(f"All Deals Count: {count}")
        if count == 2:
             print("PASS: API returned correct number of deals.")
        else:
             print("FAIL: Count mismatch.")

        # Exclude New
        print("Testing Exclude New...")
        r = requests.get('http://127.0.0.1:5000/api/deals?excluded_conditions=New', timeout=5)
        if r.status_code == 200:
            data = r.json()
            asins = [d['ASIN'] for d in data['deals']]
            print(f"ASINs returned: {asins}")

            if 'B_NEW' not in asins and 'B_USED' in asins:
                print("PASS: Exclude New logic works.")
            else:
                print(f"FAIL: Exclude New logic.")
        else:
            print(f"FAIL: API Error {r.status_code}: {r.text}")

    except Exception as e:
        print(f"Test Exception: {e}")
    finally:
        proc.terminate()

if __name__ == "__main__":
    setup_db_without_drops()
    test_api_logic()
