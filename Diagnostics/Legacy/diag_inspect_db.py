import sqlite3
import os
import sys

# Try to find the DB
POSSIBLE_PATHS = [
    os.getenv('DATABASE_URL'),
    'deals.db',
    '../deals.db',
    '/var/www/agentarbitrage/deals.db'
]

def find_db():
    for p in POSSIBLE_PATHS:
        if p and os.path.exists(p):
            return p
    return None

def inspect():
    db_path = find_db()
    if not db_path:
        print("Error: Could not find deals.db.")
        return

    print(f"Inspecting database at: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get columns
        cursor.execute("PRAGMA table_info(deals)")
        columns = [row[1] for row in cursor.fetchall()]

        print(f"Found {len(columns)} columns in 'deals' table.")
        print("-" * 30)

        # Check specific columns of interest
        targets = [
            "Sales_Rank_Current",
            "Sales_Rank___Current",
            "Categories_Sub",
            "Categories___Sub",
            "Sales_Rank_365_days_avg",
            "Sales_Rank___365_days_avg"
        ]

        for t in targets:
            if t in columns:
                print(f"[FOUND]   {t}")
            else:
                print(f"[MISSING] {t}")

        print("-" * 30)
        print("All Columns:")
        print(columns)

        # Check row count
        cursor.execute("SELECT COUNT(*) FROM deals")
        count = cursor.fetchone()[0]
        print("-" * 30)
        print(f"Total rows in 'deals' table: {count}")

    except Exception as e:
        print(f"Error inspecting DB: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    inspect()
