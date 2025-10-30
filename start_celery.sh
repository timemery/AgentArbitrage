#!/bin/bash

# This script is designed to be run from the application's root directory.

# Step 1: Ensure www-data owns the entire application directory.
# This is critical for Celery Beat to be able to create its schedule file.
chown -R www-data:www-data /var/www/agentarbitrage

# Step 1.5: Define constants for paths using ABSOLUTE paths.
APP_DIR="/var/www/agentarbitrage"
LOG_FILE="$APP_DIR/celery.log"
VENV_PYTHON="$APP_DIR/venv/bin/python" # Absolute path to the venv python
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --beat --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery purge -f"

# Step 2: Kill any lingering Celery worker processes.
echo "Attempting to stop any old Celery workers..."
pkill -f "celery -A worker.celery" || true
sleep 2

# Step 3: Purge any waiting tasks from the message queue.
echo "Purging any pending tasks from the Celery queue..."
# Must be run from the app directory to find the celery app
su -s /bin/bash -c "cd $APP_DIR && PYTHONPATH=. $PURGE_COMMAND" www-data

# Step 4: Ensure the log file AND schedule file are removed for a clean run.
echo "Ensuring log file exists at $LOG_FILE..."
rm -f $LOG_FILE
sudo rm -f $APP_DIR/celerybeat-schedule
touch $LOG_FILE
chown www-data:www-data $LOG_FILE

# Step 4.5: Ensure deals.db exists and is writable by the Celery worker.
echo "Ensuring deals.db exists and is writable..."
touch $APP_DIR/deals.db
chown www-data:www-data $APP_DIR/deals.db

# Step 5: Start the Celery worker using nohup.
echo "Starting Celery worker in the background, logging to $LOG_FILE..."
# The worker must be started from the app directory to find the modules.
su -s /bin/bash -c "cd $APP_DIR && PYTHONPATH=. nohup $WORKER_COMMAND >> $LOG_FILE 2>&1 &" www-data

sleep 2
echo "Celery worker startup command has been issued. Check status with 'ps aux | grep celery'."