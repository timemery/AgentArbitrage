#!/bin/bash

# This script is designed to be run from the application's root directory.

# Step 1: Define constants for paths.
APP_DIR="."
VENV_PYTHON="python" # Use the python in the current environment
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery purge -f"

# Step 2: Kill any lingering Celery worker processes.
echo "Attempting to stop any old Celery workers..."
pkill -f "celery -A worker.celery" || true
sleep 2

# Step 3: Purge any waiting tasks from the message queue.
echo "Purging any pending tasks from the Celery queue..."
$PURGE_COMMAND

# Step 4: Start the Celery worker using nohup, redirecting output to /dev/null.
echo "Starting Celery worker in the background..."
nohup $WORKER_COMMAND > /dev/null 2>&1 &

sleep 2
echo "Celery worker startup command has been issued. Check status with 'ps aux | grep celery'."