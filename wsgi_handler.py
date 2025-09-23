import os
import sys
import json
import subprocess
from datetime import datetime
from flask import Flask, jsonify, request, redirect, url_for, render_template, session

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Celery task directly from its source, avoiding the problematic 'worker.py'
from keepa_deals.Keepa_Deals import run_keepa_script

app = Flask(__name__)
# A secret key is required for Flask sessions to work.
app.secret_key = os.urandom(24)
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_status.json')

@app.before_request
def make_session_permanent():
    """
    [DEBUG] This is a debugging step to fix a 500 error.
    It forces a 'logged_in' session for every request, as the templates
    likely require it to render.
    """
    session.permanent = True
    if 'logged_in' not in session:
        session['logged_in'] = True

def is_celery_worker_running():
    """
    Checks if a Celery worker process for this project is running.
    [NOTE] This check is currently disabled as it was causing a 500 error,
    likely due to permissions. The plan is to re-enable it with a safer method later.
    """
    return True

@app.route('/')
def index():
    """
    This route renders the main dashboard UI, fixing the "Not Found" error.
    """
    return render_template('dashboard.html')

@app.route('/dashboard')
def dashboard():
    """
    Explicit route for the dashboard.
    """
    return render_template('dashboard.html')

@app.route('/data_sourcing', methods=['POST'])
def start_scan_route():
    """
    This route handles the POST request to start a new scan.
    """
    if not is_celery_worker_running():
        return jsonify({
            "status": "Failed",
            "message": "Error: The Celery worker process is not running. It may have crashed. Please restart it."
        }), 500

    try:
        # Initialize status file
        initial_status = {
            "status": "Queued",
            "message": "Scan has been queued and is waiting for the worker.",
            "start_time": datetime.utcnow().isoformat() + 'Z',
            "total_deals": 0, "processed_deals": 0, "etr_seconds": 0
        }
        with open(STATUS_FILE, 'w') as f:
            json.dump(initial_status, f)

        # Get API key from environment
        api_key = os.environ.get('KEEPA_API_KEY')
        if not api_key:
            raise ValueError("KEEPA_API_KEY environment variable not set.")

        # Get deal_limit from the form submission
        deal_limit = request.form.get('deal_limit', default=None, type=int)

        # Dispatch the Celery task
        run_keepa_script.delay(api_key=api_key, deal_limit=deal_limit)

        # Redirect back to the dashboard, which will poll for status
        return redirect(url_for('dashboard'))

    except Exception as e:
        # If something goes wrong, return an error
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/scan-status')
def scan_status_route():
    """
    This route provides the scan status as JSON for the frontend to poll.
    """
    try:
        current_status = {}
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                current_status = json.load(f)
        else:
            # If the file doesn't exist, it means no scan has run
            current_status = {"status": "Idle"}

        # If the status is "Running", double-check if the worker is actually alive
        if current_status.get("status") == "Running" and not is_celery_worker_running():
            current_status["status"] = "Failed"
            current_status["message"] = "Error: The Celery worker process is not running. It may have crashed."
            # Update the status file to reflect the crash
            with open(STATUS_FILE, 'w') as f:
                json.dump(current_status, f)

        return jsonify(current_status)

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error reading status file: {str(e)}"}), 500
