import os
import sys
import logging
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO)

# Append cwd to path so we can import wsgi_handler
sys.path.append(os.getcwd())

# Load .env
load_dotenv()

import json

# Mock redis BEFORE importing maintenance_tasks
# This allows running the script without a running Redis server
sys.modules['redis'] = MagicMock()

from keepa_deals.maintenance_tasks import homogenize_intelligence_task
import wsgi_handler

def main():
    print("Starting homogenization verification...")
    try:
        # Check list size first
        with open(wsgi_handler.INTELLIGENCE_FILE, 'r') as f:
            data = json.load(f)
            print(f"Current Intelligence List Size: {len(data)}")

        # Call the Celery task synchronously
        print("Triggering task...")
        # Since we mocked redis, the task won't actually update status in Redis,
        # but it should run the logic.
        removed = homogenize_intelligence_task()
        print(f"Homogenization complete. Removed: {removed}")

        # Check list size after
        with open(wsgi_handler.INTELLIGENCE_FILE, 'r') as f:
            new_data = json.load(f)
            print(f"New Intelligence List Size: {len(new_data)}")

    except Exception as e:
        print(f"Error during homogenization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
