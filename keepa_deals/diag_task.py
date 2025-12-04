
import os
import logging
from dotenv import load_dotenv
from worker import celery_app as celery
# Note: The import is wrapped in a try...except block to handle potential
# issues during the API call itself, which is the point of this diagnostic.
try:
    from keepa_deals.keepa_api import get_token_status
except ImportError as e:
    get_token_status = None
    IMPORT_ERROR = e

# Use Celery's logger
logger = logging.getLogger(__name__)

@celery.task(name="keepa_deals.diag_task.run_api_connectivity_test")
def run_api_connectivity_test():
    """
    A simple diagnostic task to test basic Keepa API connectivity from within a Celery worker.
    """
    logger.info("--- [DIAGNOSTIC TASK STARTED] ---")
    logger.info("Attempting to test Keepa API connectivity...")

    if get_token_status is None:
        logger.error(f"[DIAGNOSTIC][CRITICAL FAILURE] Failed to import 'get_token_status'. Error: {IMPORT_ERROR}")
        logger.info("--- [DIAGNOSTIC TASK FINISHED WITH ERROR] ---")
        return

    try:
        # The celery worker should already have the env loaded by the startup script,
        # but we call this just in case for direct testing.
        load_dotenv()
        api_key = os.getenv("KEEPA_API_KEY")
        if not api_key:
            logger.error("[DIAGNOSTIC] KEEPA_API_KEY not found in environment. The task cannot proceed.")
            logger.info("--- [DIAGNOSTIC TASK FINISHED WITH ERROR] ---")
            return

        logger.info("[DIAGNOSTIC] API Key loaded successfully.")
        logger.info("[DIAGNOSTIC] Calling get_token_status()...")

        # The actual API call
        status_data = get_token_status(api_key)

        if status_data and 'tokensLeft' in status_data:
            tokens_left = status_data['tokensLeft']
            logger.info(f"[DIAGNOSTIC][SUCCESS] Successfully connected to Keepa API.")
            logger.info(f"[DIAGNOSTIC] API reports {tokens_left} tokens remaining.")
        else:
            logger.error(f"[DIAGNOSTIC][FAILURE] API call failed. The function returned: {status_data}")

    except Exception as e:
        logger.error(f"[DIAGNOSTIC][CRITICAL FAILURE] An unexpected exception occurred: {e}", exc_info=True)

    finally:
        logger.info("--- [DIAGNOSTIC TASK FINISHED] ---")
