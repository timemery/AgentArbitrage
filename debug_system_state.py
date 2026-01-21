import sqlite3
import datetime
import os

DB_PATH = 'deals.db'

def check_system_state():
    if not os.path.exists(DB_PATH):
        print("deals.db not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM system_state")
        rows = cursor.fetchall()
        print("--- System State ---")
        for row in rows:
            print(row)

        cursor.execute("SELECT COUNT(*) FROM deals")
        count = cursor.fetchone()[0]
        print(f"--- Deal Count: {count} ---")

    except Exception as e:
        print(f"Error reading DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_system_state()
