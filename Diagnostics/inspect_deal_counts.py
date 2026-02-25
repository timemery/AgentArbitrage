
import sqlite3
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Path relative to CWD (root of repo)
DB_PATH = 'deals.db'

def inspect_counts():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Total Count
            cursor.execute("SELECT COUNT(*) FROM deals")
            total = cursor.fetchone()[0]
            print(f"Total Deals in DB: {total}")

            # 2. Rescued Count
            cursor.execute("SELECT COUNT(*) FROM deals WHERE source='stale_rescue'")
            rescued = cursor.fetchone()[0]
            print(f"Deals from 'stale_rescue': {rescued}")

            # 3. Unprofitable Count (Hidden from Dashboard)
            cursor.execute("SELECT COUNT(*) FROM deals WHERE Profit <= 0")
            unprofitable = cursor.fetchone()[0]
            print(f"Unprofitable Deals (Profit <= 0): {unprofitable}")

            # 4. Visible Estimate (Total - Unprofitable)
            # Note: Dashboard has other filters, but this is the main one
            visible_est = total - unprofitable
            print(f"Estimated Visible Deals: {visible_est}")

            # 5. Stale but not deleted yet (> 48h)
            cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc < datetime('now', '-48 hours')")
            stale_pending = cursor.fetchone()[0]
            print(f"Deals > 48h old (Pending Rescue/Deletion): {stale_pending}")

            # 6. Check if any are clamped (List at != integer/standard)
            # Just sampling
            cursor.execute("SELECT `List at`, `Amazon - Current` FROM deals LIMIT 5")
            rows = cursor.fetchall()
            print("Sample Price Data:")
            for r in rows:
                print(f"  List: {r['List at']}, Amz: {r['Amazon - Current']}")

    except Exception as e:
        print(f"Error inspecting DB: {e}")

if __name__ == "__main__":
    inspect_counts()
