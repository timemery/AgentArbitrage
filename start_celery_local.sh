#!/bin/bash

# This script is designed for a local/sandbox environment.
# It starts Redis, the Celery worker, and Celery Beat scheduler in a resilient loop.

# Step 1: Define constants
APP_DIR=$(pwd)
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"
MONITOR_LOG_FILE="$APP_DIR/celery_monitor.log"

# Define the commands
WORKER_COMMAND="celery -A worker.celery_app worker --loglevel=INFO"
BEAT_COMMAND="celery -A worker.celery_app beat --loglevel=INFO"
PURGE_COMMAND="celery -A worker.celery_app purge -f"

# --- Main Resiliency Loop (to be run in the background) ---
monitor_and_restart() {
    while true; do
        # Ensure Redis is running
        echo "Checking Redis status and starting if not running..." >> "$MONITOR_LOG_FILE"
        redis-cli ping > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Redis not responding. Starting Redis server..." >> "$MONITOR_LOG_FILE"
            sudo redis-server > redis.log 2>&1 &
            sleep 5
            redis-cli ping > /dev/null 2>&1
            if [ $? -ne 0 ]; then
                echo "CRITICAL: Failed to start Redis. Waiting before retry." >> "$MONITOR_LOG_FILE"
                sleep 60
                continue
            fi
            echo "Redis started successfully." >> "$MONITOR_LOG_FILE"
        else
            echo "Redis is already running." >> "$MONITOR_LOG_FILE"
        fi

        # Kill any old Celery processes
        echo "Attempting to stop any old Celery processes..." >> "$MONITOR_LOG_FILE"
        pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found." >> "$MONITOR_LOG_FILE"
        sleep 2

        # Purge tasks and clean up state
        echo "Purging tasks and cleaning state..." >> "$MONITOR_LOG_FILE"
        $PURGE_COMMAND
        rm -f "$APP_DIR/celerybeat-schedule"
        touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"

        # Start the daemons
        set -a
        source .env
        set +a

        echo "Starting Celery worker and beat scheduler daemons..." >> "$MONITOR_LOG_FILE"
        nohup $WORKER_COMMAND > "$WORKER_LOG_FILE" 2>&1 &
        WORKER_PID=$!
        nohup $BEAT_COMMAND > "$BEAT_LOG_FILE" 2>&1 &
        BEAT_PID=$!

        echo "Services started. Monitoring PIDs: Worker=$WORKER_PID, Beat=$BEAT_PID" >> "$MONITOR_LOG_FILE"

        # Monitor loop
        while kill -0 $WORKER_PID > /dev/null 2>&1 && kill -0 $BEAT_PID > /dev/null 2>&1; do
            sleep 30
        done

        echo "Detected a service failure. Waiting for 10 seconds before restarting..." >> "$MONITOR_LOG_FILE"
        kill $WORKER_PID > /dev/null 2>&1
        kill $BEAT_PID > /dev/null 2>&1
        sleep 10
    done
}

# --- Script Entry Point ---
if pgrep -f "start_celery_local.sh" | grep -v $$ > /dev/null; then
    echo "The resilient startup script is already running in the background. To restart, kill the existing process first."
    exit 1
fi

nohup bash -c 'monitor_and_restart' >> "$MONITOR_LOG_FILE" 2>&1 &
disown

echo "The resilient Celery service monitor has been started in the background."
echo "You can now safely close this terminal. To see the monitor's logs, run:"
echo "tail -f $MONITOR_LOG_FILE"
echo "To see worker/beat logs, run:"
echo "tail -f $WORKER_LOG_FILE"
echo "tail -f $BEAT_LOG_FILE"
