import sqlite3
import sys
import logging
from keepa_deals.db_utils import get_db_connection
from keepa_deals.business_calculations import load_settings
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate():
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Step 0: Clean up DISMISSED tombstones
        cursor.execute("DELETE FROM inventory_ledger WHERE status = 'DISMISSED' AND source = 'Dashboard'")
        deleted_tombstones = cursor.rowcount
        logger.info(f"Cleaned up {deleted_tombstones} DISMISSED tombstones from inventory_ledger.")

        # Step 1: Identify rows to migrate
        cursor.execute("SELECT * FROM inventory_ledger WHERE status = 'PURCHASED' AND source = 'Dashboard'")
        rows_to_migrate = cursor.fetchall()

        count_to_migrate = len(rows_to_migrate)
        logger.info(f"Found {count_to_migrate} manually-purchased rows to migrate.")

        if count_to_migrate == 0:
            conn.commit()  # Commit the tombstone cleanup at least
            logger.info("No rows to migrate. Exiting successfully.")
            return

        settings = load_settings()
        prep_fee = float(settings.get('prep_fee_per_book', 0.0))
        logger.info(f"Using prep_fee_at_purchase = {prep_fee} for all backfilled rows.")

        inserted_count = 0
        deleted_count = 0

        for row in rows_to_migrate:
            cursor.execute("""
                INSERT INTO confirmed_buys (
                    asin, condition, buy_cost, purchase_date, quantity_purchased,
                    prep_fee_at_purchase,
                    snapshot_list_at, snapshot_fba_fee, snapshot_referral_pct, snapshot_shipping_included,
                    snapshot_estimated_tax, snapshot_estimated_shipping, snapshot_prep_fee
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['asin'],
                '4',
                row['buy_cost'] if row['buy_cost'] is not None else 0.0,
                row['purchase_date'] if row['purchase_date'] else datetime.utcnow().isoformat(),
                row['quantity_purchased'] if row['quantity_purchased'] else 1,
                prep_fee,
                row['snapshot_list_at'],
                row['snapshot_fba_fee'],
                row['snapshot_referral_pct'],
                row['snapshot_shipping_included'],
                row['snapshot_estimated_tax'],
                row['snapshot_estimated_shipping'],
                row['snapshot_prep_fee']
            ))

            inserted_count += 1

            cursor.execute("DELETE FROM inventory_ledger WHERE id = ?", (row['id'],))
            deleted_count += cursor.rowcount

        if inserted_count != count_to_migrate or deleted_count != count_to_migrate:
            conn.rollback()
            logger.error(f"Mismatch in migration: To migrate {count_to_migrate}, Inserted {inserted_count}, Deleted {deleted_count}. Rolled back.")
            sys.exit(1)

        conn.commit()
        logger.info(f"Successfully migrated {count_to_migrate} rows. Committed transaction.")

    except Exception as e:
        if 'conn' in locals():
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Migration failed: {e}. Rolled back.")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    migrate()