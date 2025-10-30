import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deals.db')
TABLE_NAME = 'deals'

print("--- Running Database Check Script ---")
if not os.path.exists(DB_PATH):
    print(f"Error: Database file not found at '{DB_PATH}'")
else:
    conn = None
    try:
        print(f"Connecting to database at '{DB_PATH}'...")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print(f"Checking row count in table '{TABLE_NAME}'...")
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        count = cursor.fetchone()[0]
        print(f"Total rows in '{TABLE_NAME}': {count}")

        if count > 0:
            print("Fetching the first row to inspect data...")
            cursor.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 1")
            first_row = cursor.fetchone()
            
            if first_row:
                print("First row data (as dictionary):")
                print(dict(first_row))
            else:
                print("Could not fetch the first row, even though count > 0.")

    except sqlite3.Error as e:
        print(f"An SQLite error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")
print("--- Script Finished ---")