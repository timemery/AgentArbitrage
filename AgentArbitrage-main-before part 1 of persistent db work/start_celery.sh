#!/bin/bash

# This script is designed to be run from the application's root directory on the server.

# Step 1: Define constants for paths.
APP_DIR="/var/www/agentarbitrage"
LOG_FILE="$APP_DIR/celery.log"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery purge -f" # -f forces purge without confirmation

# Step 2: Kill any lingering Celery worker processes for this specific application.
echo "Attempting to stop any old Celery workers for agentarbitrage..."
# Use pkill to find and kill processes matching the specific celery worker command.
sudo pkill -f "$WORKER_COMMAND" || true
sleep 2

# Step 3: Purge any waiting tasks from the message queue to prevent auto-starts.
echo "Purging any pending tasks from the Celery queue..."
# This is run as www-data from the app directory to ensure it has the correct context.
sudo -u www-data sh -c "cd $APP_DIR && $PURGE_COMMAND"

# Step 4: Ensure the log file exists and has correct permissions.
echo "Ensuring log file exists at $LOG_FILE and is owned by www-data..."
sudo touch $LOG_FILE
sudo chown www-data:www-data $LOG_FILE

# Step 5: Start the Celery worker using nohup for robust backgrounding.
echo "Starting Celery worker as www-data in the background using nohup..."
# The worker is started via nohup to ensure it persists, with all output sent to the log file.
sudo -u www-data sh -c "cd $APP_DIR && nohup $WORKER_COMMAND >> $LOG_FILE 2>&1 &"

sleep 2 # Give the process a moment to start up.
echo "Celery worker startup command has been issued. Check status with 'ps aux | grep celery'."