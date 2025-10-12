# trigger_simple_task.py
import logging
from keepa_deals.simple_task import get_recent_deals_asins
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Triggers the get_recent_deals_asins Celery task.
    """
    load_dotenv() # Make sure environment variables are loaded
    logger.info("Triggering the 'get_recent_deals_asins' task...")
    
    # Using .delay() will send the task to the Celery queue to be executed by a worker.
    # Make sure your Celery worker is running before executing this script.
    task_result = get_recent_deals_asins.delay()
    
    logger.info(f"Task has been sent to the queue. Task ID: {task_result.id}")
    logger.info("Please check the Celery worker logs for execution details.")
    logger.info("You can verify the result by running check_db.py after the task completes.")

if __name__ == "__main__":
    main()