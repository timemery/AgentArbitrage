import sqlite3
import os
import sys

def migrate():
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from keepa_deals.db_utils import DB_PATH, get_db_connection

    print(f"Connecting to database at {DB_PATH}")

    conn = get_db_connection(DB_PATH)
    cursor = conn.cursor()

    columns_to_add = [
        "snapshot_list_at REAL",
        "snapshot_fba_fee REAL",
        "snapshot_referral_pct REAL",
        "snapshot_shipping_included REAL",
        "snapshot_estimated_tax REAL",
        "snapshot_estimated_shipping REAL",
        "snapshot_prep_fee REAL"
    ]

    cursor.execute("PRAGMA table_info(inventory_ledger);")
    existing_columns = [col[1] for col in cursor.fetchall()]

    for col_def in columns_to_add:
        col_name = col_def.split()[0]
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE inventory_ledger ADD COLUMN {col_def}")
                print(f"Added column: {col_name}")
            except sqlite3.Error as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()

    print("Migration complete. Verifying schema:")

    conn = get_db_connection(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(inventory_ledger);")
    final_columns = [col[1] for col in cursor.fetchall()]
    conn.close()

    added_cols = [c.split()[0] for c in columns_to_add]
    missing = [c for c in added_cols if c not in final_columns]

    if not missing:
        print("SUCCESS: All 7 snapshot columns are present.")
    else:
        print(f"FAILURE: Missing columns: {missing}")

if __name__ == "__main__":
    migrate()
