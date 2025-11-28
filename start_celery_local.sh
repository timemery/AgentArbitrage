#!/bin/bash

# This script is designed for a local/sandbox environment.
# It starts the Celery worker and Celery Beat scheduler as separate daemons.

# Step 1: Define constants
APP_DIR=$(pwd)
VENV_PYTHON="$APP_DIR/venv/bin/python" # Assuming a venv exists, adjust if not
# If no venv, use system python. This is less ideal.
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"

# Define the commands for the worker and scheduler
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO"
BEAT_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app beat --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app purge -f"

# Step 2: Kill any old Celery processes
echo "Attempting to stop any old Celery processes..."
pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found."
sleep 2

# Step 3: Purge any waiting tasks
echo "Purging any pending tasks from the message queue..."
$PURGE_COMMAND

# Step 4: Clean up old state and prepare files
echo "Preparing log files and cleaning scheduler state..."
rm -f "$APP_DIR/celerybeat-schedule"
touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"

# Step 5: Start the daemons
# Common environment setup
ENV_SETUP="set -a && source .env && set +a"

# Start the Celery Worker daemon
echo "Starting Celery worker daemon..."
eval "$ENV_SETUP"
nohup $WORKER_COMMAND >> $WORKER_LOG_FILE 2>&1 &

# Start the Celery Beat Scheduler daemon
echo "Starting Celery Beat scheduler daemon..."
eval "$ENV_SETUP"
nohup $BEAT_COMMAND >> $BEAT_LOG_FILE 2>&1 &

sleep 2
echo "Celery worker and beat scheduler daemons have been started."
echo "You can now monitor their logs independently:"
echo "tail -f $WORKER_LOG_FILE"
echo "tail -f $BEAT_LOG_FILE"
