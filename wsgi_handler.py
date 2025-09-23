# /var/www/agentarbitrage/wsgi_handler.py
import os
import sys
import json
import subprocess
from datetime import datetime

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Celery task directly from its source file.
# This avoids any potential import issues with the 'worker.py' module.
from keepa_deals.Keepa_Deals import run_keepa_script

# Define the path for the status file
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_status.json')

def is_celery_worker_running():
    """
    Checks if a Celery worker process for this project is running.
    [NOTE] This check is currently disabled. It was causing a 500 error,
    likely due to permissions. The plan is to re-enable it with a safer method later.
    """
    return True

def application(environ, start_response):
    path = environ.get('PATH_INFO', '')

    if path == '/data_sourcing':
        # --- LIVENESS CHECK ---
        if not is_celery_worker_running():
            status_data = {
                "status": "Failed",
                "message": "Error: The Celery worker process is not running. It may have crashed. Please restart it.",
                "end_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            }
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump(status_data, f)
            except IOError:
                pass

            response_body = json.dumps(status_data)
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'application/json'), ('Content-Length', str(len(response_body)))]
            start_response(status, headers)
            return [response_body.encode('utf-8')]
        # --- END LIVENESS CHECK ---

        try:
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

            api_key = os.environ.get('KEEPA_API_KEY')
            if not api_key:
                raise ValueError("KEEPA_API_KEY environment variable not set.")

            query_string = environ.get('QUERY_STRING', '')
            params = dict(p.split('=') for p in query_string.split('&')) if query_string else {}
            deal_limit = int(params.get('deal_limit')) if 'deal_limit' in params else None

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
            current_status = {}
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    current_status = json.load(f)

            if current_status.get("status") == "Running" and not is_celery_worker_running():
                current_status["status"] = "Failed"
                current_status["message"] = "Error: The Celery worker process is not running. It may have crashed."
                current_status["end_time"] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                with open(STATUS_FILE, 'w') as f:
                    json.dump(current_status, f)

            response_body = json.dumps(current_status)
            status = '200 OK'
        except FileNotFoundError:
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
        response_body = b'Not Found'
        headers = [('Content-Type', 'text/plain'), ('Content-Length', str(len(response_body)))]
        start_response(status, headers)
        return [response_body]
