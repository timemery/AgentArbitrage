# trigger_diag.py
import sys
from celery import Celery

# This script sends a task to the Celery worker to run our diagnostic function.

# Add the project root to the Python path to allow direct imports
sys.path.append('.')

try:
    # We must create a minimal Celery app instance to send the task
    # It must connect to the same broker as the worker.
    celery_app = Celery('diag_trigger')
    celery_app.config_from_object('celery_config')
    print("Successfully connected to Celery broker.")

except Exception as e:
    print(f"Error: Could not connect to the Celery broker (Redis).")
    print("Please ensure Redis is running and accessible at the broker URL specified in celery_config.py.")
    print(f"Details: {e}")
    sys.exit(1)

# The name of the task to trigger
task_name = 'keepa_deals.env_diag.log_worker_environment'

print(f"\nSending task '{task_name}' to the worker...")

try:
    # Send the task
    result = celery_app.send_task(task_name)
    print(f"Task sent successfully! Task ID: {result.id}")
    print("\nThe worker should now execute the diagnostic task.")
    print("Please check for a file named 'diag_output.log' in your application's root directory.")
    print("It may take a moment for the file to appear.")

except Exception as e:
    print(f"\nError: Failed to send the task to the worker.")
    print("This could mean the worker is down or there is a problem with the broker connection.")
    print(f"Details: {e}")
