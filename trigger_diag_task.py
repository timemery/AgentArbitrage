
import sys
from worker import celery_app as celery

def trigger_diagnostic_task():
    """
    Sends the API connectivity diagnostic task to the Celery queue.
    """
    try:
        print("--- Triggering the API Connectivity Diagnostic Task ---")
        # Send the task by its registered name
        celery.send_task("keepa_deals.diag_task.run_api_connectivity_test")
        print("\n[SUCCESS] Diagnostic task sent to the queue.")
        print("You should now monitor the Celery worker logs to see the result.")
        print("Run: 'tail -f celery_worker.log'")

    except Exception as e:
        print(f"\n[ERROR] Failed to send task to the queue: {e}", file=sys.stderr)
        print("Please ensure that Redis is running and Celery is correctly configured.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    trigger_diagnostic_task()
