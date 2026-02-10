
import sqlite3
import os
import sys
import json
from unittest.mock import patch

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import sanitize_col_name, create_deals_table_if_not_exists, DB_PATH

TEST_DB = "test_schema_migration_verify.db"
HEADERS_PATH = os.path.join(os.getcwd(), 'keepa_deals', 'headers.json')

def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print(f"Creating test DB: {TEST_DB}")
    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()

    # 1. Create table with OLD schema (minimal)
    c.execute("""
        CREATE TABLE deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ASIN TEXT NOT NULL UNIQUE,
            "Title" TEXT,
            "Price_Now" REAL,
            "last_seen_utc" TIMESTAMP,
            "source" TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("Created table with minimal schema.")

    # 2. Call the patched migration function
    # We need to mock DB_PATH inside db_utils so it points to our test DB
    print("Running migration...")
    with patch('keepa_deals.db_utils.DB_PATH', TEST_DB):
        create_deals_table_if_not_exists()

    # 3. Verify Schema
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("PRAGMA table_info(deals)")
    columns = [row['name'] for row in c.fetchall()]

    # Load headers to check against
    with open(HEADERS_PATH) as f:
        headers = json.load(f)

    missing_cols = []
    for h in headers:
        sanitized = sanitize_col_name(h)
        if sanitized not in columns:
            missing_cols.append(sanitized)

    if missing_cols:
        print(f"FAILURE: Migration failed to add columns: {missing_cols}")
        conn.close()
        return
    else:
        print("SUCCESS: All columns from headers.json are present in the DB.")

    # 4. Verify Insert
    sanitized_headers = [sanitize_col_name(h) for h in headers]
    sanitized_headers.extend(['last_seen_utc', 'source'])

    row_data = {h: None for h in sanitized_headers}
    row_data['ASIN'] = 'TESTASIN999'
    row_data['Title'] = 'Test Product Post Migration'
    if 'Detailed_Seasonality' in sanitized_headers:
        row_data['Detailed_Seasonality'] = 'Migration Success'

    cols_str = ', '.join(f'"{h}"' for h in sanitized_headers)
    vals_str = ', '.join(['?'] * len(sanitized_headers))
    sql = f"INSERT INTO deals ({cols_str}) VALUES ({vals_str})"
    data_tuple = tuple(row_data[h] for h in sanitized_headers)

    try:
        c.execute(sql, data_tuple)
        conn.commit()
        print("SUCCESS: Insert operation succeeded with new columns.")
    except Exception as e:
        print(f"FAILURE: Insert failed: {e}")

    conn.close()

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

if __name__ == "__main__":
    main()
