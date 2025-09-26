#!/bin/bash

# This script is designed to be run from the application's root directory.

# Step 1: Kill any lingering Celery worker processes.
# We add '|| true' so the script doesn't exit if no processes are found.
echo "Attempting to stop any old Celery workers..."
pkill -f 'celery' || true
sleep 2

# Step 2: Ensure the log file for the Celery worker exists.
LOG_FILE="/var/www/agentarbitrage/celery.log"
echo "Ensuring log file exists at $LOG_FILE..."
touch $LOG_FILE

# Step 3: Start the Celery worker as a detached background process.
VENV_PYTHON="/var/www/agentarbitrage/venv/bin/python"
echo "Starting Celery worker in detached mode..."
$VENV_PYTHON -m celery -A celery_config.celery worker --detach --loglevel=DEBUG --logfile=$LOG_FILE

echo "Celery worker startup command issued."