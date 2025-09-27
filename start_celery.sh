#!/bin/bash

# This script is designed to be run from the application's root directory.

# Step 1: Kill any lingering Celery worker processes.
echo "Attempting to stop any old Celery workers..."
sudo pkill -f 'celery' || true
sleep 2

# Step 2: Define constants for paths to avoid repetition.
APP_DIR="/var/www/agentarbitrage"
LOG_FILE="$APP_DIR/celery.log"
VENV_PYTHON="$APP_DIR/venv/bin/python"

# Step 3: Ensure the log file for the Celery worker exists and has correct permissions.
echo "Ensuring log file exists at $LOG_FILE and is owned by www-data..."
sudo touch $LOG_FILE
sudo chown www-data:www-data $LOG_FILE

# Step 4: Start the Celery worker as www-data in a new subshell to handle permissions correctly.
echo "Starting Celery worker as www-data in the background..."
# The `sh -c "..."` ensures that the cd, the command, the redirection, and the backgrounding all happen as the www-data user.
sudo -u www-data sh -c "cd $APP_DIR && $VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO >> $LOG_FILE 2>&1 &"

echo "Celery worker startup command has been issued."