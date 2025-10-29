#!/bin/bash
# start_celery_local.sh

echo "--- Starting Celery Worker Locally ---"

# Add current directory to PYTHONPATH to ensure modules are found
export PYTHONPATH=$PYTHONPATH:.

# Define constants for local execution
LOG_FILE="celery.log"
# Correctly point to the celery app instance inside the worker.py module
WORKER_COMMAND="python3 -m celery -A worker.celery worker --beat --loglevel=INFO"
PURGE_COMMAND="python3 -m celery -A worker.celery purge -f"

# Kill any lingering Celery worker processes.
echo "Attempting to stop any old Celery workers..."
pkill -f "celery -A" || true
sleep 2

# Purge any waiting tasks from the message queue.
echo "Purging any pending tasks from the Celery queue..."
$PURGE_COMMAND

# Ensure the log file AND schedule file are removed for a clean run.
echo "Resetting log file and schedule..."
rm -f $LOG_FILE
rm -f ./celerybeat-schedule
touch $LOG_FILE

# Ensure deals.db exists.
echo "Ensuring deals.db exists..."
touch ./deals.db

# Start the Celery worker in the background.
echo "Starting Celery worker in the background, logging to $LOG_FILE..."
nohup $WORKER_COMMAND > $LOG_FILE 2>&1 &

sleep 3
echo "Celery worker startup command has been issued."
echo "Check status with: 'ps aux | grep celery'"
echo "Monitor logs with: 'tail -f celery.log'"
