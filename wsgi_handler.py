# /var/www/agentarbitrage/wsgi_handler.py
import os
import sys
import json
import subprocess
from datetime import datetime

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Celery task
from worker import run_keepa_script

# Define the path for the status file
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_status.json')

def is_celery_worker_running():
    """
    Checks if a Celery worker process for this project is running.
    This is a more robust check to prevent the UI from getting stuck.
    """
    try:
        # Use pgrep to find processes matching the Celery worker command pattern
        # The pattern 'celery -A worker.celery worker' is specific to our startup command
        command = "pgrep -f 'celery -A worker.celery worker'"
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # If pgrep finds a process, it returns a non-empty output with exit code 0
        return True
    except subprocess.CalledProcessError:
        # pgrep returns a non-zero exit code if no process is found
        return False

def application(environ, start_response):
    path = environ.get('PATH_INFO', '')

    if path == '/data_sourcing':
        # --- LIVENESS CHECK ---
        # Before starting a new scan, check if a worker is actually running.
        if not is_celery_worker_running():
            # If no worker is running, update the status to reflect this and prevent a new scan.
            status_data = {
                "status": "Failed",
                "message": "Error: The Celery worker process is not running. It may have crashed. Please restart it.",
                "end_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            }
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump(status_data, f)
            except IOError:
                pass # If we can't write the status, we still proceed to inform the user

            response_body = json.dumps(status_data)
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'application/json'), ('Content-Length', str(len(response_body)))]
            start_response(status, headers)
            return [response_body.encode('utf-8')]
        # --- END LIVENESS CHECK ---

        # If worker is running, proceed to start the task
        try:
            # Initialize status file at the beginning of a scan request
            initial_status = {
                "status": "Queued",
                "message": "Scan has been queued and is waiting for the worker.",
                "start_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
                "end_time": None,
                "total_deals": 0,
                "processed_deals": 0,
                "etr_seconds": 0,
                "output_file": None
            }
            with open(STATUS_FILE, 'w') as f:
                json.dump(initial_status, f)

            # Get the API key from environment variables
            api_key = os.environ.get('KEEPA_API_KEY')
            if not api_key:
                raise ValueError("KEEPA_API_KEY environment variable not set.")

            # Get deal_limit from query string, default to None (no limit)
            query_string = environ.get('QUERY_STRING', '')
            params = dict(p.split('=') for p in query_string.split('&')) if query_string else {}
            deal_limit = int(params.get('deal_limit')) if 'deal_limit' in params else None

            # Asynchronously call the Celery task
            run_keepa_script.delay(api_key=api_key, deal_limit=deal_limit)
            
            response_body = json.dumps({"status": "success", "message": "Scan initiated."})
            status = '200 OK'
        except Exception as e:
            response_body = json.dumps({"status": "error", "message": str(e)})
            status = '500 Internal Server Error'
        
        headers = [('Content-Type', 'application/json'), ('Content-Length', str(len(response_body)))]
        start_response(status, headers)
        return [response_body.encode('utf-8')]

    elif path == '/scan-status':
        try:
            # --- LIVENESS CHECK ON STATUS ---
            # Before returning the status, check if the worker is alive, but only if the status is "Running".
            # This prevents the UI from being stuck on "Running" if the worker has crashed silently.
            current_status = {}
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    current_status = json.load(f)

            if current_status.get("status") == "Running" and not is_celery_worker_running():
                # The status file says we are running, but we can't find a worker process.
                # The worker has crashed. Update the status file to reflect this.
                current_status["status"] = "Failed"
                current_status["message"] = "Error: The Celery worker process is not running. It may have crashed."
                current_status["end_time"] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                with open(STATUS_FILE, 'w') as f:
                    json.dump(current_status, f)
            # --- END LIVENESS CHECK ---

            response_body = json.dumps(current_status)
            status = '200 OK'
        except FileNotFoundError:
            # If status file doesn't exist, return a default "Not Started" state
            default_status = {"status": "Not Started", "message": "No scan has been initiated yet."}
            response_body = json.dumps(default_status)
            status = '200 OK'
        except Exception as e:
            response_body = json.dumps({"status": "error", "message": f"Error reading status file: {str(e)}"})
            status = '500 Internal Server Error'

        headers = [('Content-Type', 'application/json'), ('Content-Length', str(len(response_body)))]
        start_response(status, headers)
        return [response_body.encode('utf-8')]

    else:
        status = '404 Not Found'
        response_body = 'Not Found'
        headers = [('Content-Type', 'text/plain'), ('Content-Length', str(len(response_body)))]
        start_response(status, headers)
        return [response_body.encode('utf-8')]