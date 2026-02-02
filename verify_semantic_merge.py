import os
import sys
import logging

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO)

# Append cwd to path so we can import wsgi_handler
sys.path.append(os.getcwd())

import json
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
        removed = homogenize_intelligence_task()
        print(f"Homogenization complete. Removed: {removed}")
    except Exception as e:
        print(f"Error during homogenization: {e}")

if __name__ == "__main__":
    main()
