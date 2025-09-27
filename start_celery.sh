#!/bin/bash

# This script is designed to be run from the application's root directory on the server.

# Step 1: Define constants for paths.
APP_DIR="/var/www/agentarbitrage"
LOG_FILE="$APP_DIR/celery.log"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO"

# Step 2: Kill any lingering Celery worker processes for this specific application.
echo "Attempting to stop any old Celery workers for agentarbitrage..."
# Use pkill to find and kill processes matching the specific celery worker command.
# Using the full command string makes this very specific and safe.
sudo pkill -f "$WORKER_COMMAND" || true
sleep 2

# Step 3: Ensure the log file exists and has correct permissions.
echo "Ensuring log file exists at $LOG_FILE and is owned by www-data..."
sudo touch $LOG_FILE
sudo chown www-data:www-data $LOG_FILE

# Step 4: Start the Celery worker using nohup for robust backgrounding.
echo "Starting Celery worker as www-data in the background using nohup..."
# We use 'nohup' to ensure the process isn't terminated when the shell closes.
# The command is run as www-data to maintain correct permissions.
# We change to the application directory *within the sudo command* to ensure the
# worker starts in the correct location.
# All output (stdout & stderr) is redirected to the log file.
# The '&' at the end sends the command to the background.
sudo -u www-data sh -c "cd $APP_DIR && nohup $WORKER_COMMAND >> $LOG_FILE 2>&1 &"

sleep 2 # Give the process a moment to start up.
echo "Celery worker startup command has been issued. Check status with 'ps aux | grep celery'."