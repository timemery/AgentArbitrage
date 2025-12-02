#!/bin/bash

# This script is designed for a local/sandbox environment.
# It starts Redis, the Celery worker, and Celery Beat scheduler in a resilient loop.

# Step 1: Define constants
APP_DIR=$(pwd)
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"

# Define the commands
WORKER_COMMAND="celery -A worker.celery_app worker --loglevel=INFO"
BEAT_COMMAND="celery -A worker.celery_app beat --loglevel=INFO"
PURGE_COMMAND="celery -A worker.celery_app purge -f"

# --- Main Resiliency Loop ---
while true; do
    # Step 2: Ensure Redis is running
    echo "Checking Redis status and starting if not running..."
    redis-cli ping > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Redis not responding. Starting Redis server..."
        sudo redis-server > redis.log 2>&1 &
        sleep 5 # Give Redis a moment to start
        redis-cli ping > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "CRITICAL: Failed to start Redis. Waiting before retry."
            sleep 60
            continue
        fi
        echo "Redis started successfully."
    else
        echo "Redis is already running."
    fi

    # Step 3: Kill any old Celery processes
    echo "Attempting to stop any old Celery processes..."
    pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found."
    sleep 2

    # Step 4: Purge tasks and clean up state
    echo "Purging any pending tasks from the message queue..."
    $PURGE_COMMAND

    echo "Preparing log files and cleaning scheduler state..."
    rm -f "$APP_DIR/celerybeat-schedule"
    touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"

    # Step 5: Start the daemons
    set -a
    source .env
    set +a

    echo "Starting Celery worker and beat scheduler daemons..."
    nohup $WORKER_COMMAND > "$WORKER_LOG_FILE" 2>&1 &
    WORKER_PID=$!
    nohup $BEAT_COMMAND > "$BEAT_LOG_FILE" 2>&1 &
    BEAT_PID=$!

    echo "Services started. The script will now monitor and restart them if they crash."
    echo "Worker PID: $WORKER_PID, Beat PID: $BEAT_PID"
    echo "You can monitor logs at: $WORKER_LOG_FILE and $BEAT_LOG_FILE"

    # Step 6: Monitor loop
    while kill -0 $WORKER_PID > /dev/null 2>&1 && kill -0 $BEAT_PID > /dev/null 2>&1; do
        sleep 30
    done

    echo "Detected a service failure. Waiting for 10 seconds before attempting to restart..."
    # Kill any remaining process before restarting
    kill $WORKER_PID > /dev/null 2>&1
    kill $BEAT_PID > /dev/null 2>&1
    sleep 10
done
