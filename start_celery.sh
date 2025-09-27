#!/bin/bash

# This script is designed to be run from the application's root directory on the server.

# Step 1: Kill any lingering Celery worker processes for this specific application.
echo "Attempting to stop any old Celery workers for agentarbitrage..."
# Use pkill to find and kill processes matching the specific celery worker command for this app.
# The `|| true` prevents the script from exiting if no processes are found.
sudo pkill -f "/var/www/agentarbitrage/venv/bin/python -m celery -A worker.celery worker" || true
sleep 2

# Step 2: Define constants for paths to avoid repetition and ensure clarity.
APP_DIR="/var/www/agentarbitrage"
LOG_FILE="$APP_DIR/celery.log"
PID_FILE="$APP_DIR/celery.pid"
VENV_PYTHON="$APP_DIR/venv/bin/python"

# Step 3: Ensure the log and pid files exist and have correct permissions.
echo "Ensuring log and pid files exist and are owned by www-data..."
sudo touch $LOG_FILE
sudo chown www-data:www-data $LOG_FILE
sudo touch $PID_FILE
sudo chown www-data:www-data $PID_FILE

# Step 4: Start the Celery worker as www-data using a robust, combined approach.
echo "Starting Celery worker as www-data in the background..."
# The `sudo -u www-data sh -c "..."` ensures that the directory change (cd) and the
# celery command are both executed as the 'www-data' user in the same subshell.
# The --detach flag tells Celery to run as a background daemon.
sudo -u www-data sh -c "cd $APP_DIR && $VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO --detach --logfile=$LOG_FILE --pidfile=$PID_FILE"

echo "Celery worker startup command has been issued."