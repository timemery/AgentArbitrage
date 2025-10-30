# Restoring Dashboard Functionality
# trigger_backfill_task.py

import sys
import os

# This ensures the script can find the 'keepa_deals' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Corrected Import: The celery app instance is exposed via the 'worker' module.
from worker import celery as celery_app
# Corrected Import: Use the function that handles its own DB connection and clears the table.
from keepa_deals.db_utils import recreate_deals_table

def main():
    """
    Triggers the backfill_deals Celery task.
    This script is the official way to start the initial, full data population.
    It will first clear the existing deals table to ensure a fresh start.
    """
    print("--- Triggering Celery Backfill Task ---")

    try:
        # Recreate the database table before starting a new backfill.
        # This function handles its own connection and drops the old table.
        print("Recreating the 'deals' table for a fresh start...")
        recreate_deals_table()
        print("Table recreated successfully.")

        print("Sending 'backfill_deals' task to the Celery worker...")
        # Send the task by its registered name
        celery_app.send_task('keepa_deals.backfiller.backfill_deals')

        print("\n[SUCCESS] Task sent to the queue.")
        print("You should now monitor the Celery worker logs to see the progress.")
        print("Run: 'tail -f celery.log'")

    except Exception as e:
        print(f"\n[ERROR] Failed to send task: {e}")
        print("Please ensure that the Celery worker and Redis server are running.")

if __name__ == "__main__":
    main()
