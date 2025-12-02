#!/bin/bash

# This script is designed for a production environment.
# It starts Redis, the Celery worker, and Celery Beat scheduler in a resilient loop.

# Step 1: Set ownership
echo "Ensuring www-data owns the entire application directory..."
chown -R www-data:www-data /var/www/agentarbitrage

# Step 2: Define constants
APP_DIR="/var/www/agentarbitrage"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"

# Define the commands
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO"
BEAT_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app beat --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app purge -f"

# Common environment setup to be used for both processes
ENV_SETUP="cd $APP_DIR && set -a && source .env && set +a && PYTHONPATH=."

# --- Main Resiliency Loop ---
while true; do
    # Step 3: Ensure Redis is running
    # This is idempotent. If Redis is running, it does nothing. If it's not, it starts it.
    echo "Checking Redis status and starting if not running..."
    redis-cli ping > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Redis not responding. Starting Redis server..."
        sudo redis-server > /var/log/redis/redis-server.log 2>&1 &
        sleep 5 # Give Redis a moment to start
        # Verify it started correctly
        redis-cli ping > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "CRITICAL: Failed to start Redis. Cannot continue. Waiting before retry."
            sleep 60
            continue # Skip to the next loop iteration
        fi
        echo "Redis started successfully."
    else
        echo "Redis is already running."
    fi

    # Step 4: Kill any old/zombie Celery processes before starting new ones
    echo "Attempting to stop any old Celery processes..."
    pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found."
    sleep 2

    # Step 5: Purge tasks and clean up state
    echo "Purging any pending tasks from the message queue..."
    su -s /bin/bash -c "cd $APP_DIR && PYTHONPATH=. $PURGE_COMMAND" www-data

    echo "Preparing log files and cleaning scheduler state..."
    sudo rm -f "$APP_DIR/celerybeat-schedule"
    touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"
    chown www-data:www-data "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"
    touch "$APP_DIR/deals.db"
    chown www-data:www-data "$APP_DIR/deals.db"

    # Step 6: Start the daemons
    echo "Starting Celery worker and beat scheduler daemons..."
    su -s /bin/bash -c "$ENV_SETUP nohup $WORKER_COMMAND >> $WORKER_LOG_FILE 2>&1 &" www-data
    su -s /bin/bash -c "$ENV_SETUP nohup $BEAT_COMMAND >> $BEAT_LOG_FILE 2>&1 &" www-data

    echo "Services started. The script will now monitor and restart them if they crash."
    echo "You can monitor logs at: $WORKER_LOG_FILE and $BEAT_LOG_FILE"

    # Step 7: Monitor loop
    # This loop checks if the processes are alive. If either dies, the outer loop will restart everything.
    while true; do
        # Check if the worker process is running
        if ! pgrep -f "$WORKER_COMMAND" > /dev/null; then
            echo "Celery worker process appears to have crashed. Restarting all services..."
            break # Exit the monitor loop to trigger a full restart
        fi
        # Check if the beat process is running
        if ! pgrep -f "$BEAT_COMMAND" > /dev/null; then
            echo "Celery beat process appears to have crashed. Restarting all services..."
            break # Exit the monitor loop to trigger a full restart
        fi
        sleep 30 # Check every 30 seconds
    done

    echo "Detected a service failure. Waiting for 10 seconds before attempting to restart..."
    sleep 10
done
