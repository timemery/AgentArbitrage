# trigger_diag_task.py

import sys
import os

# This ensures the script can find the 'worker' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from worker import celery_app

def main():
    """
    Triggers the run_environment_diagnostic Celery task.
    """
    print("--- Triggering Environment Diagnostic Task ---")
    try:
        # Use the registered task name to send the task
        celery_app.send_task('keepa_deals.env_diag.run_environment_diagnostic')

        print("\n[SUCCESS] Diagnostic task sent to the queue.")
        print("Please now check the contents of 'diag_output.log' after a moment.")
        print("Run: 'cat diag_output.log'")

    except Exception as e:
        print(f"\n[ERROR] Failed to send task: {e}")
        print("Please ensure that the Celery worker and Redis server are running.")

if __name__ == "__main__":
    main()
