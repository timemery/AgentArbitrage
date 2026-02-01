#!/bin/bash

# This script is designed for a production environment.
# Updated Jan 31 2026: Added PID cleanup check
# It starts Redis, the Celery worker, and Celery Beat scheduler in a resilient loop.

# Step 1: Set ownership
echo "Ensuring www-data owns the entire application directory..."
chown -R www-data:www-data /var/www/agentarbitrage

# --- Main Resiliency Loop (to be run in the background) ---
monitor_and_restart() {
    # Define constants INSIDE the function to ensure they are available in the subshell
    APP_DIR="/var/www/agentarbitrage"
    VENV_PYTHON="$APP_DIR/venv/bin/python"
    WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
    BEAT_LOG_FILE="$APP_DIR/celery_beat.log"
    MONITOR_LOG_FILE="$APP_DIR/celery_monitor.log"
    WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO --concurrency=4"
    BEAT_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app beat --loglevel=INFO"
    PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app purge -f"
    ENV_SETUP="set -a && source $APP_DIR/.env && set +a"

    # Ensure Redis is running
    echo "Checking Redis status and starting if not running..." >> "$MONITOR_LOG_FILE"
    redis-cli ping > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Redis not responding. Starting Redis server..." >> "$MONITOR_LOG_FILE"
        sudo redis-server > /var/log/redis/redis-server.log 2>&1 &
        sleep 5
        redis-cli ping > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "CRITICAL: Failed to start Redis. Aborting." >> "$MONITOR_LOG_FILE"
            return 1
        fi
        echo "Redis started successfully." >> "$MONITOR_LOG_FILE"
    else
        echo "Redis is already running." >> "$MONITOR_LOG_FILE"
    fi

    # Kill any old/zombie Celery processes
    echo "Attempting to stop any old Celery processes..." >> "$MONITOR_LOG_FILE"
    pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found." >> "$MONITOR_LOG_FILE"
    sleep 2

    # Purge tasks and clean up state
    echo "Purging tasks and cleaning state..." >> "$MONITOR_LOG_FILE"
    su -s /bin/bash -c "$ENV_SETUP && $PURGE_COMMAND" www-data
    sudo rm -f "$APP_DIR/celerybeat-schedule"
    sudo rm -f "$APP_DIR/celerybeat.pid" # Ensure stale PID doesn't block startup
    touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE" "$APP_DIR/deals.db"
    chown www-data:www-data "$WORKER_LOG_FILE" "$BEAT_LOG_FILE" "$APP_DIR/deals.db"

    # Start the daemons using the 'su' command for reliability in this environment
    # The inner 'nohup' is removed as the parent monitor is already nohup'd.
    echo "Starting Celery worker and beat scheduler daemons..." >> "$MONITOR_LOG_FILE"
    su -s /bin/bash -c "cd $APP_DIR && $ENV_SETUP && $WORKER_COMMAND >> $WORKER_LOG_FILE 2>&1 &" www-data
    su -s /bin/bash -c "cd $APP_DIR && $ENV_SETUP && $BEAT_COMMAND >> $BEAT_LOG_FILE 2>&1 &" www-data

    echo "Services started. Entering monitoring loop..." >> "$MONITOR_LOG_FILE"

    # Infinite Loop to keep services running
    while true; do
        sleep 60

        # Check Worker
        if ! pgrep -f "celery -A worker.celery_app worker" > /dev/null; then
            echo "$(date): Celery Worker died. Restarting..." >> "$MONITOR_LOG_FILE"
            su -s /bin/bash -c "cd $APP_DIR && $ENV_SETUP && $WORKER_COMMAND >> $WORKER_LOG_FILE 2>&1 &" www-data
        fi

        # Check Beat
        if ! pgrep -f "celery -A worker.celery_app beat" > /dev/null; then
            echo "$(date): Celery Beat died. Restarting..." >> "$MONITOR_LOG_FILE"
            # Cleanup PID before restart
            sudo rm -f "$APP_DIR/celerybeat.pid"
            su -s /bin/bash -c "cd $APP_DIR && $ENV_SETUP && $BEAT_COMMAND >> $BEAT_LOG_FILE 2>&1 &" www-data
        fi

        # Check Redis
        redis-cli ping > /dev/null 2>&1
        if [ $? -ne 0 ]; then
             echo "$(date): Redis died. Restarting..." >> "$MONITOR_LOG_FILE"
             sudo redis-server > /var/log/redis/redis-server.log 2>&1 &
        fi
    done
}

# --- Script Entry Point ---
# Check if the monitor is already running
# We search for the unique "monitor_and_restart" string which is the actual background process.
# This is more robust than checking for the script name itself, which caused false positives.
if pgrep -f "monitor_and_restart" > /dev/null; then
    echo "The resilient Celery monitor is already running in the background."
    echo "To force a full restart, please run the following commands:"
    echo "  sudo pkill -f \"monitor_and_restart\""
    echo "  ./kill_everything.sh"
    echo "  sudo ./start_celery.sh"
    exit 1
fi

# Export the function so it's available to the subshell
export -f monitor_and_restart

# Define MONITOR_LOG_FILE here just for the initial nohup redirection
MONITOR_LOG_FILE="/var/www/agentarbitrage/celery_monitor.log"

# Launch the monitor function in the background and disown it
nohup bash -c 'monitor_and_restart' >> "$MONITOR_LOG_FILE" 2>&1 &
disown

echo "The resilient Celery service monitor has been started in the background."
echo "You can now safely close this terminal. To see the monitor's logs, run:"
echo "tail -f $MONITOR_LOG_FILE"
echo "To see worker/beat logs, run:"
echo "tail -f /var/www/agentarbitrage/celery_worker.log"
echo "tail -f /var/www/agentarbitrage/celery_beat.log"
