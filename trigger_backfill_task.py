# Restoring Dashboard Functionality
# trigger_backfill_task.py

import sys
import os

# This ensures the script can find the 'keepa_deals' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Corrected Import: The celery app instance is exposed via the 'worker' module.
from celery import chain
from worker import celery_app
# Import the tasks themselves to create signatures
from keepa_deals.backfiller import backfill_deals
from keepa_deals.importer_task import import_deals
# Corrected Import: Use the function that handles its own DB connection and clears the table.
from keepa_deals.db_utils import recreate_deals_table

def main():
    """
    Triggers a chained workflow: backfill_deals -> import_deals.
    This is the official way to start the full data population process.
    The import task will run automatically only after the backfill task succeeds.
    """
    print("--- Triggering Celery Backfill Workflow (backfill -> import) ---")

    try:
        # The backfiller task now handles table recreation, so we don't need to do it here.

        print("Creating and sending the chained workflow to the Celery worker...")

        # Create a chain of task signatures. The '.s()' creates a signature.
        workflow = chain(backfill_deals.s(), import_deals.s())

        # Execute the workflow
        workflow.apply_async()

        print("\n[SUCCESS] Workflow sent to the queue.")
        print("You should now monitor the Celery worker logs to see the progress.")
        print("Run: 'tail -f celery.log'")

    except Exception as e:
        print(f"\n[ERROR] Failed to send task: {e}")
        print("Please ensure that the Celery worker and Redis server are running.")

if __name__ == "__main__":
    main()
