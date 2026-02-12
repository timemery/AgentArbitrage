
import subprocess
import time
import re
from datetime import datetime

LOG_FILE = "/var/www/agentarbitrage/celery_worker.log"

def main():
    print(f"--- Checking for successful upserts in {LOG_FILE} ---")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # Grep for "Successfully saved" or "Task Complete"
        # We want to see recent activity.
        # "Task Complete: Processed X scanned, upserted Y."
        
        cmd = f"tail -n 500 {LOG_FILE} | grep -E 'Task Complete|Successfully saved|Stop Trigger'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        if not lines or lines == ['']:
            print("No completed tasks or upserts found in the last 500 log lines yet.")
            print("The worker is likely still processing the first batch.")
        else:
            print(f"Found {len(lines)} relevant log entries:")
            for line in lines[-5:]: # Show last 5
                print(f"  {line}")
                
    except Exception as e:
        print(f"Error checking logs: {e}")

if __name__ == "__main__":
    main()
