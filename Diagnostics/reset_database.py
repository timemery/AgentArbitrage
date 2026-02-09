#!/usr/bin/env python3
import sys
import os
import logging

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import recreate_deals_table, recreate_user_restrictions_table, DB_PATH

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Manually resets the database tables (deals and user_restrictions).
    This mimics the functionality of the old 'backfill_deals(reset=True)' flag.
    """
    print("!!! WARNING: DATABASE RESET !!!")
    print(f"This will delete ALL data in '{DB_PATH}'.")
    print("Tables to be cleared: 'deals', 'user_restrictions'")

    confirm = input("Are you sure you want to proceed? (Type 'YES' to confirm): ")
    if confirm.strip() != "YES":
        print("Reset aborted.")
        return

    try:
        logger.info("Starting database reset...")
        recreate_deals_table()
        recreate_user_restrictions_table()
        logger.info("Database reset complete. All data has been cleared.")
        print("\n[SUCCESS] Database reset complete.")
        print("The Smart Ingestor will now start fresh on its next run (via Celery Beat).")

    except Exception as e:
        logger.error(f"Failed to reset database: {e}", exc_info=True)
        print(f"\n[ERROR] Failed to reset database: {e}")

if __name__ == "__main__":
    main()
