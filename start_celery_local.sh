#!/bin/bash

# This script is designed for a local/sandbox environment.
# It starts Redis, the Celery worker, and Celery Beat scheduler.

# Step 1: Start Redis Server
echo "Starting Redis server in the background..."
sudo redis-server > redis.log 2>&1 &
sleep 2

# Step 2: Define constants
APP_DIR=$(pwd)
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"

# Define the commands
WORKER_COMMAND="celery -A worker.celery_app worker --loglevel=INFO"
BEAT_COMMAND="celery -A worker.celery_app beat --loglevel=INFO"
PURGE_COMMAND="celery -A worker.celery_app purge -f"

# Step 3: Kill any old Celery processes
echo "Attempting to stop any old Celery processes..."
pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found."
sleep 2

# Step 4: Purge any waiting tasks
echo "Purging any pending tasks from the message queue..."
$PURGE_COMMAND

# Step 5: Clean up old state and prepare files
echo "Preparing log files and cleaning scheduler state..."
rm -f "$APP_DIR/celerybeat-schedule"
touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"

# Step 6: Start the daemons
# Source environment variables before running the processes
set -a
source .env
set +a

# Start the Celery Worker daemon
echo "Starting Celery worker daemon..."
nohup $WORKER_COMMAND > "$WORKER_LOG_FILE" 2>&1 &

# Start the Celery Beat Scheduler daemon
echo "Starting Celery Beat scheduler daemon..."
nohup $BEAT_COMMAND > "$BEAT_LOG_FILE" 2>&1 &

sleep 2
echo "Celery worker and beat scheduler daemons have been started."
echo "You can now monitor their logs:"
echo "tail -f $WORKER_LOG_FILE"
echo "tail -f $BEAT_LOG_FILE"
