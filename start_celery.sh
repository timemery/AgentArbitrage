#!/bin/bash

# THIS IS A TEMPORARY DIAGNOSTIC SCRIPT.

# Step 1: Define constants for paths.
APP_DIR="."
VENV_PYTHON="python" # Use the python in the current environment
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --beat --loglevel=INFO"

# Step 2: Kill any lingering Celery worker processes.
echo "Attempting to stop any old Celery workers..."
pkill -f "celery -A worker.celery" || true
sleep 2

# Step 3: Remove the schedule file for a clean run.
echo "Removing schedule file..."
rm -f $APP_DIR/celerybeat-schedule

# Step 4: Run the worker directly in the foreground.
echo "Starting Celery worker in the FOREGROUND to capture errors..."
$WORKER_COMMAND
