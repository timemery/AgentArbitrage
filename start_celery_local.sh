#!/bin/bash

# This script is designed to be run from the application's root directory
# and is adapted for a local/sandbox environment.

# Step 1: Define constants for paths using RELATIVE paths.
APP_DIR=$(pwd)
LOG_FILE="$APP_DIR/celery.log"
# Use the python3 in the current environment's PATH
PYTHON_EXEC="python3"
WORKER_COMMAND="$PYTHON_EXEC -m celery -A worker.celery_app worker --beat --loglevel=INFO"
PURGE_COMMAND="$PYTHON_EXEC -m celery -A worker.celery_app purge -f"

# Step 2: Kill any lingering Celery worker processes.
echo "Attempting to stop any old Celery workers..."
# Use pkill with a pattern that matches the local command
pkill -f "celery -A worker.celery" || echo "No old Celery workers found."
sleep 2

# Step 3: Purge any waiting tasks from the message queue.
echo "Purging any pending tasks from the Celery queue..."
# Run the command directly as the current user
$PURGE_COMMAND

# Step 4: Ensure the log file AND schedule file are removed for a clean run.
echo "Ensuring log file exists at $LOG_FILE..."
rm -f "$LOG_FILE"
rm -f "$APP_DIR/celerybeat-schedule"
touch "$LOG_FILE"

# Step 4.5: Ensure deals.db exists.
echo "Ensuring deals.db exists..."
touch "$APP_DIR/deals.db"

# Step 5: Start the Celery worker using nohup.
echo "Starting Celery worker in the background, logging to $LOG_FILE..."
# Run the worker directly, in the background.
nohup $WORKER_COMMAND >> "$LOG_FILE" 2>&1 &

sleep 2
echo "Celery worker startup command has been issued. Check status with 'ps aux | grep celery'."
