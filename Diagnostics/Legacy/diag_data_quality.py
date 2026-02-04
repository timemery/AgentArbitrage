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

def check_quality():
    db_path = find_db()
    if not db_path:
        print("Error: Could not find deals.db.")
        return

    print(f"Inspecting data quality in: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Columns of interest
        cols = [
            "ASIN",
            "Seller", "Seller_Quality_Score",
            "1yr_Avg", "Best_Price",
            "Percent_Down", "Trend",
            "Detailed_Seasonality"
        ]

        # Check if columns exist first
        cursor.execute("PRAGMA table_info(deals)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        valid_cols = [c for c in cols if c in existing_cols]
        missing_cols = [c for c in cols if c not in existing_cols]

        if missing_cols:
            print(f"WARNING: Missing columns in DB: {missing_cols}")

        query_cols = ", ".join([f'"{c}"' for c in valid_cols])
        sql = f"SELECT {query_cols} FROM deals LIMIT 5"

        cursor.execute(sql)
        rows = cursor.fetchall()

        if not rows:
            print("No deals found in table.")
            return

        print("-" * 80)
        # Print header
        header = " | ".join([f"{c:<20}" for c in valid_cols])
        print(header)
        print("-" * 80)

        for row in rows:
            values = []
            for c in valid_cols:
                val = row[c]
                val_str = str(val) if val is not None else "None"
                # Truncate if too long
                if len(val_str) > 18:
                    val_str = val_str[:15] + "..."
                values.append(f"{val_str:<20}")
            print(" | ".join(values))

        print("-" * 80)

    except Exception as e:
        print(f"Error inspecting DB: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    check_quality()
