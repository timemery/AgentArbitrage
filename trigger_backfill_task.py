# trigger_backfill_task.py
import logging
from celery_app import celery_app
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def main():
    """
    Triggers the backfill_deals Celery task by name.
    """
    load_dotenv() # Make sure environment variables are loaded
    print("Triggering the 'keepa_deals.backfiller.backfill_deals' task by name...")

    # Send the task by its registered name to avoid direct imports
    task_result = celery_app.send_task('keepa_deals.backfiller.backfill_deals')

    print(f"Task has been sent to the queue. Task ID: {task_result.id}")
    logger.info("Please check the Celery worker logs for execution details.")
    logger.info("You can verify the result by running check_db.py after the task completes and checking for watermark.json.")

if __name__ == "__main__":
    main()
