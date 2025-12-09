import os
import sys
import logging

# Configure logging to see output from the task
logging.basicConfig(level=logging.INFO)

# Add the project root to the Python path to allow for correct module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from keepa_deals.simple_task import update_recent_deals
from dotenv import load_dotenv

if __name__ == "__main__":
    print("--- Running diagnostic for simple_task ---")

    # Load environment variables from the root .env file
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        print("Loaded environment variables from .env file.")
    else:
        print("Warning: .env file not found. The script may fail if it relies on environment variables.")

    try:
        print("Attempting to execute update_recent_deals task directly...")
        # We call the function directly to simulate how the Celery worker would execute it.
        # This allows us to catch the UnboundLocalError in a controlled environment.
        update_recent_deals()
        print("--- Diagnostic script finished. If no errors appeared above, the task ran successfully. ---")
    except Exception as e:
        print(f"--- Diagnostic script failed with an error: ---")
        import traceback
        traceback.print_exc()
