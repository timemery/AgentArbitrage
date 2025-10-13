# trigger_backfill_task.py
import logging
from keepa_deals.backfiller import backfill_deals
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def main():
    """
    Triggers the backfill_deals Celery task.
    """
    load_dotenv() # Make sure environment variables are loaded
    logger.info("Triggering the 'backfill_deals' task...")

    # Using .delay() will send the task to the Celery queue to be executed by a worker.
    # Make sure your Celery worker is running before executing this script.
    task_result = backfill_deals.delay()

    logger.info(f"Task has been sent to the queue. Task ID: {task_result.id}")
    logger.info("Please check the Celery worker logs for execution details.")
    logger.info("You can verify the result by running check_db.py after the task completes and checking for watermark.json.")

if __name__ == "__main__":
    main()
