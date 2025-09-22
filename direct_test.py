import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set up basic logging for the test
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from keepa_deals.Keepa_Deals import run_keepa_script
except ImportError as e:
    logging.error(f"Failed to import run_keepa_script. This indicates a problem with the PYTHONPATH or a circular import. Error: {e}")
    sys.exit(1)


def main():
    """
    Directly invokes the keepa scan script without involving Celery.
    This is for debugging purposes to isolate issues in the script from the task queue.
    """
    logging.info("--- Running direct test script ---")

    # Load environment variables from .env file
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(dotenv_path):
        logging.error(f".env file not found at {dotenv_path}")
        # As a fallback for this test, let's try to get it from the environment anyway
        KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
    else:
        load_dotenv(dotenv_path=dotenv_path)
        KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")

    if not KEEPA_API_KEY:
        logging.error("KEEPA_API_KEY not found in environment or .env file. Cannot proceed.")
        return

    logging.info("KEEPA_API_KEY loaded, starting script...")

    try:
        # When calling a celery task function directly, the bound 'self' argument must be provided.
        # We can pass None as it's not used when running outside of a Celery worker context.
        # The last argument 'status_update_callback' is also for celery/flask integration, we can pass None.
        run_keepa_script(KEEPA_API_KEY, no_cache=True, deal_limit=3)
        logging.info("--- Direct test script finished successfully ---")
    except Exception as e:
        logging.error("An exception occurred while running the script directly.", exc_info=True)
        logging.error(f"--- Direct test script failed: {e} ---")


if __name__ == "__main__":
    main()
