
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

            print("\nFirst 10 Rows:")
            print(f"{'ID':<5} {'SKU':<20} {'ASIN':<15} {'Qty Rem':<10} {'Qty Pur':<10} {'Status':<10}")
            print("-" * 75)

            cursor.execute("SELECT id, sku, asin, quantity_remaining, quantity_purchased, status FROM inventory_ledger LIMIT 10")
            rows = cursor.fetchall()
            for row in rows:
                # Handle None values safely
                r_id = str(row[0] if row[0] is not None else 'None')
                r_sku = str(row[1] if row[1] is not None else 'None')
                r_asin = str(row[2] if row[2] is not None else 'None')
                r_qrem = str(row[3] if row[3] is not None else 'None')
                r_qpur = str(row[4] if row[4] is not None else 'None')
                r_stat = str(row[5] if row[5] is not None else 'None')

                print(f"{r_id:<5} {r_sku:<20} {r_asin:<15} {r_qrem:<10} {r_qpur:<10} {r_stat:<10}")

    except Exception as e:
        print(f"Error dumping DB: {e}")

if __name__ == "__main__":
    dump_ledger()
