
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from keepa_deals.db_utils import DB_PATH

def purge_zombies():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    print(f"--- Connecting to database: {DB_PATH} ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Identify Zombies
        # Conditions matches strict logic in processing.py
        query = """
            SELECT ASIN, "List at", "1yr. Avg.", "Profit"
            FROM deals
            WHERE
                "Profit" <= 0 OR
                "Profit" IS NULL OR
                "List at" IN ('-', 'N/A', '0', '0.0', '0.00', '') OR "List at" IS NULL OR
                "1yr. Avg." IN ('-', 'N/A', '0', '0.0', '0.00', '') OR "1yr. Avg." IS NULL
        """

        cursor.execute(query)
        zombies = cursor.fetchall()

        count = len(zombies)
        print(f"Found {count} Zombie Deals (Negative Profit or Missing Data).")

        if count > 0:
            print("Examples:")
            for z in zombies[:5]:
                print(f"  ASIN: {z[0]}, List at: {z[1]}, 1yr Avg: {z[2]}, Profit: {z[3]}")

            # 2. Delete
            print(f"Purging {count} records...")
            delete_query = """
                DELETE FROM deals
                WHERE
                    "Profit" <= 0 OR
                    "Profit" IS NULL OR
                    "List at" IN ('-', 'N/A', '0', '0.0', '0.00', '') OR "List at" IS NULL OR
                    "1yr. Avg." IN ('-', 'N/A', '0', '0.0', '0.00', '') OR "1yr. Avg." IS NULL
            """
            cursor.execute(delete_query)
            conn.commit()
            print("Purge complete.")
        else:
            print("Database is clean! No zombies found.")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    purge_zombies()
