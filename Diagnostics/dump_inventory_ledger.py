
import sqlite3
import os

# Database Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deals.db')

def dump_ledger():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check count
            cursor.execute("SELECT COUNT(*) FROM inventory_ledger")
            count = cursor.fetchone()[0]
            print(f"Total rows in inventory_ledger: {count}")

            # Check Active count
            cursor.execute("SELECT COUNT(*) FROM inventory_ledger WHERE quantity_remaining > 0")
            active_count = cursor.fetchone()[0]
            print(f"Active rows (quantity_remaining > 0): {active_count}")

            # Check FBA count (inference)
            # We don't have an is_fba column in the DB schema, but we can check if quantity_remaining > 0 and status is PURCHASED

            print("\nFirst 10 Rows:")
            print(f"{'ID':<5} {'SKU':<20} {'ASIN':<15} {'Qty Rem':<10} {'Qty Pur':<10} {'Status':<10}")
            print("-" * 75)

            cursor.execute("SELECT id, sku, asin, quantity_remaining, quantity_purchased, status FROM inventory_ledger LIMIT 10")
            rows = cursor.fetchall()
            for row in rows:
                print(f"{row[0]:<5} {row[1]:<20} {row[2]:<15} {row[3]:<10} {row[4]:<10} {row[5]:<10}")

    except Exception as e:
        print(f"Error dumping DB: {e}")

if __name__ == "__main__":
    dump_ledger()
