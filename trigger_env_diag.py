
import sys
from worker import celery_app as celery

def trigger_env_diagnostic_task():
    """
    Sends the environment diagnostic task to the Celery queue.
    """
    try:
        print("--- Triggering the Celery Worker Environment Diagnostic Task ---")
        # Send the task by its registered name, which is defined in the keepa_deals/env_diag.py file
        celery.send_task("keepa_deals.env_diag.log_environment_details")
        print("\n[SUCCESS] Environment diagnostic task sent to the queue.")
        print("This is a critical test. Please monitor the Celery worker logs for the output.")
        print("Run: 'tail -f celery_worker.log'")

    except Exception as e:
        print(f"\n[ERROR] Failed to send task to the queue: {e}", file=sys.stderr)
        print("Please ensure that Redis is running and Celery is correctly configured.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    trigger_env_diagnostic_task()
