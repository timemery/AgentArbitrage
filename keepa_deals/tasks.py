# keepa_deals/tasks.py
import logging
from celery_app import celery_app
from .Keepa_Deals import run_keepa_script as run_keepa_script_main
import os

logger = logging.getLogger(__name__)

@celery_app.task(name='keepa_deals.tasks.run_keepa_script')
def run_keepa_script_task(no_cache=False, output_dir='data'):
    """
    Celery task wrapper for the main Keepa script.
    It retrieves the API key from environment variables and calls the main function.
    """
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("KEEPA_API_KEY not found in environment. Aborting task.")
        return

    try:
        # We don't pass the status_update_callback from here as it's not serializable.
        # The main function has a default implementation that writes to a status file.
        run_keepa_script_main(
            api_key=api_key,
            no_cache=no_cache,
            output_dir=output_dir,
            deal_limit=None, # Explicitly set to None to ensure no limit is used
            status_update_callback=None
        )
    except Exception as e:
        logger.error(f"An error occurred while running the Keepa script task: {e}", exc_info=True)
        # Re-raise the exception to mark the task as failed in Celery
        raise
