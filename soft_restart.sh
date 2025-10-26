#!/bin/bash
set -e

echo "--- (As www-data) BEGINNING SOFT RESTART ---"

# This script is designed to be run as the www-data user from the application root.
# e.g., sudo -u www-data /var/www/agentarbitrage/soft_restart.sh
# It assumes services like Apache and Redis are managed separately by a privileged user.

echo "--> Step 1: Stopping any running Celery workers..."
# As www-data, this will only kill workers running as the same user.
pkill -f 'celery' || true
sleep 2

echo "--> Step 2: Cleaning Python cache and old Celery schedule..."
# Ensure paths are relative to the application directory where the script is run.
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete
rm -f celerybeat-schedule

# Define variables
# Use a relative path for the virtual environment
VENV_PYTHON="./venv/bin/python"
LOG_FILE="./celery.log"
APP_DIR="."

echo "--> Step 3: Purging any old tasks from the message queue..."
$VENV_PYTHON -m celery -A worker.celery purge -f

echo "--> Step 4: Triggering web server reload via touch..."
# This will gracefully reload the mod_wsgi application if Apache is configured to watch wsgi.py
touch wsgi.py

echo "--> Step 5: Starting new Celery worker in the background..."
# Ensure the log file exists and is writable by the current user (www-data).
touch $LOG_FILE

# The core fix: Run nohup directly as the current user (www-data), which is the correct way.
nohup $VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO --beat >> $LOG_FILE 2>&1 &

echo ""
echo "--- (As www-data) SYSTEM RESTART COMMANDS ISSUED ---"
echo "Please wait ~15 seconds for the worker to start."
echo "You can monitor its progress with: tail -f celery.log"
echo "NOTE: This script does not manage root services (e.g., Apache, Redis)."
