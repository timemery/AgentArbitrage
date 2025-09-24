#!/bin/bash

# This script is designed to be run from the application's root directory: /var/www/agentarbitrage/

# Step 1: Kill any lingering Celery worker processes to ensure a clean start.
echo "Attempting to stop any old Celery workers..."
pkill -f 'celery'

# It's good practice to wait a moment to let the processes die.
sleep 2

# Step 2: Ensure the log file for the Celery worker exists.
LOG_FILE="/var/www/agentarbitrage/celery.log"
echo "Ensuring log file exists at $LOG_FILE..."
touch $LOG_FILE

# Step 3: Start the Celery worker as a detached background process.
VENV_PYTHON="/var/www/agentarbitrage/venv/bin/python"
echo "Starting Celery worker in detached mode..."
$VENV_PYTHON -m celery -A worker.celery worker --detach --loglevel=INFO --logfile=$LOG_FILE

echo "Celery worker startup command issued."
