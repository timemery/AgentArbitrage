# trigger_backfill_task.py

import sys
import os
import argparse

# This ensures the script can find the 'keepa_deals' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from worker import celery_app
from keepa_deals.backfiller import backfill_deals

def main():
    """
    Triggers the backfill_deals Celery task.

    By default, this script triggers a resumable backfill, which will pick up
    from the last completed page.

    Use the --reset flag to start a fresh backfill. This will clear the
    backfill state and recreate the database table before starting from page 0.
    """
    parser = argparse.ArgumentParser(description='Trigger the backfill_deals Celery task.')
    parser.add_argument('--reset', action='store_true',
                        help='Perform a fresh backfill, clearing old data and state.')
    args = parser.parse_args()

    if args.reset:
        print("--- Triggering a FRESH backfill. All existing data and backfill state will be cleared. ---")
    else:
        print("--- Triggering a RESUMABLE backfill. The process will continue from the last saved state. ---")

    try:
        # The backfill_deals task now directly accepts a 'reset' parameter.
        backfill_deals.delay(reset=args.reset)

        print("\n[SUCCESS] Task sent to the queue.")
        print("You should now monitor the Celery worker logs to see the progress.")
        print("Run: 'tail -f celery_worker.log'")

    except Exception as e:
        print(f"\n[ERROR] Failed to send task: {e}")
        print("Please ensure that the Celery worker and Redis server are running.")

if __name__ == "__main__":
    main()
