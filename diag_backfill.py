# diag_backfill.py
# A script to run the backfill_deals task directly for debugging purposes.

import logging
import os
from dotenv import load_dotenv

# Configure logging to see the output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# It's crucial to load environment variables, as the task depends on them.
# Assuming the script is run from the project root.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    print("Loading .env file...")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(".env file not found. Task may fail if it relies on environment variables.")

# Make sure the app's modules are in the Python path
import sys
sys.path.append(os.getcwd())

try:
    from keepa_deals.backfiller import backfill_deals
    print("Successfully imported the backfill_deals task.")
except ImportError as e:
    print(f"Failed to import backfill_deals task: {e}")
    sys.exit(1)

if __name__ == "__main__":
    print("Attempting to run the backfill_deals task directly...")
    try:
        # We call the function directly, not via .delay() or .apply_async()
        backfill_deals()
        print("--- Direct task execution finished. ---")
    except Exception as e:
        print(f"An error occurred during direct execution of the task: {e}")
        logging.exception("Detailed traceback:")
