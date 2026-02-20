import sqlite3
import os

DB_PATH = 'join_test.db'

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create deals table with quoted ASIN
    cursor.execute('CREATE TABLE deals (id INTEGER PRIMARY KEY, "ASIN" TEXT, "Title" TEXT)')
    cursor.execute('INSERT INTO deals ("ASIN", "Title") VALUES (?, ?)', ('B001', 'Test Book'))

    # Create user_restrictions table
    cursor.execute('CREATE TABLE user_restrictions (id INTEGER PRIMARY KEY, user_id TEXT, asin TEXT, is_restricted INTEGER, approval_url TEXT)')
    cursor.execute('INSERT INTO user_restrictions (user_id, asin, is_restricted) VALUES (?, ?, ?)', ('user1', 'B001', 1))

    conn.commit()
    conn.close()

def test_join():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    user_id = 'user1'

    # Simulate api_deals query with d.ASIN (unquoted)
    try:
        sql = 'SELECT d.*, ur.is_restricted FROM deals AS d LEFT JOIN user_restrictions AS ur ON d.ASIN = ur.asin AND ur.user_id = ?'
        print(f"Executing: {sql}")
        cursor.execute(sql, (user_id,))
        rows = cursor.fetchall()
        print(f"Rows found: {len(rows)}")
        for row in rows:
            print(dict(row))
        print("PASS: Unquoted d.ASIN works.")
    except Exception as e:
        print(f"FAIL: Unquoted d.ASIN failed: {e}")

    conn.close()

if __name__ == "__main__":
    setup_db()
    test_join()
