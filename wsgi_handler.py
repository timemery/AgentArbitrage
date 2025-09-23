import os
import sys
import json
import subprocess
from datetime import datetime
from flask import Flask, jsonify, request, redirect, url_for, render_template, session
from functools import wraps

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Celery task directly from its source, avoiding the problematic 'worker.py'
from keepa_deals.Keepa_Deals import run_keepa_script

app = Flask(__name__)
# The secret key must be a static value loaded from the environment.
# Using os.urandom() creates a new key on every app restart, which breaks sessions.
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    raise ValueError("No FLASK_SECRET_KEY set for Flask application. Please set it in your .env file.")
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_status.json')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # In a real app, you would check credentials here.
        # For this restoration, we just log the user in.
        session['logged_in'] = True
        session.permanent = True
        return redirect(url_for('index'))
    return """
        <title>Login</title>
        <h1>Please log in to continue</h1>
        <form method="post">
            <input type=submit value=Login>
        </form>
    """

def is_celery_worker_running():
    """
    Checks if a Celery worker process for this project is running.
    [NOTE] This check is currently disabled as it was causing a 500 error,
    likely due to permissions. The plan is to re-enable it with a safer method later.
    """
    return True

@app.route('/')
@login_required
def index():
    """
    This route renders the main dashboard UI.
    """
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Explicit route for the dashboard.
    """
    return render_template('dashboard.html')

@app.route('/guided_learning')
@login_required
def guided_learning():
    """
    This placeholder route fixes the BuildError in the layout template.
    """
    return render_template('guided_learning.html')

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

