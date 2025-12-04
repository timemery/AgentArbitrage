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
MONITOR_LOG_FILE="$APP_DIR/celery_monitor.log"

# Define the commands - now with --workdir for robustness
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO --workdir=$APP_DIR"
BEAT_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app beat --loglevel=INFO --workdir=$APP_DIR"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app purge -f --workdir=$APP_DIR"

# Common environment setup - simplified as --workdir handles the path
ENV_SETUP="set -a && source $APP_DIR/.env && set +a"

# --- Main Resiliency Loop (to be run in the background) ---
monitor_and_restart() {
    while true; do
        # Ensure Redis is running
        echo "Checking Redis status and starting if not running..." >> "$MONITOR_LOG_FILE"
        redis-cli ping > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Redis not responding. Starting Redis server..." >> "$MONITOR_LOG_FILE"
            sudo redis-server > /var/log/redis/redis-server.log 2>&1 &
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

        # Kill any old/zombie Celery processes
        echo "Attempting to stop any old Celery processes..." >> "$MONITOR_LOG_FILE"
        pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found." >> "$MONITOR_LOG_FILE"
        sleep 2

        # Purge tasks and clean up state
        echo "Purging tasks and cleaning state..." >> "$MONITOR_LOG_FILE"
        # The --workdir flag in the command handles the directory change, simplifying the su command
        sudo -u www-data bash -c "$ENV_SETUP && $PURGE_COMMAND"
        sudo rm -f "$APP_DIR/celerybeat-schedule"
        touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE" "$APP_DIR/deals.db"
        chown www-data:www-data "$WORKER_LOG_FILE" "$BEAT_LOG_FILE" "$APP_DIR/deals.db"

        # Make the new worker launch script executable
        chmod +x "$APP_DIR/launch_worker.sh"
        chown www-data:www-data "$APP_DIR/launch_worker.sh"

        # Start the daemons using the new, robust method
        echo "Starting Celery worker and beat scheduler daemons..." >> "$MONITOR_LOG_FILE"
        sudo -u www-data bash -c "$APP_DIR/launch_worker.sh"
        sudo -u www-data bash -c "cd $APP_DIR && set -a && source .env && set +a && nohup $BEAT_COMMAND >> $BEAT_LOG_FILE 2>&1 &"

        echo "Services started. Monitoring for crashes..." >> "$MONITOR_LOG_FILE"

        # Monitor loop - simplified to check for the main worker process
        while true; do
            # The worker is launched via the launch_worker.sh script, but the process name is the celery command itself
            if ! pgrep -f "celery -A worker.celery_app worker" > /dev/null; then
                echo "Celery worker process appears to have crashed. Restarting all services..." >> "$MONITOR_LOG_FILE"
                break
            fi
             if ! pgrep -f "celery -A worker.celery_app beat" > /dev/null; then
                echo "Celery beat process appears to have crashed. Restarting all services..." >> "$MONITOR_LOG_FILE"
                break
            fi
            sleep 30
        done

        echo "Detected a service failure. Waiting for 10 seconds before restarting..." >> "$MONITOR_LOG_FILE"
        sleep 10
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

# Launch the monitor function in the background and disown it
nohup bash -c 'monitor_and_restart' >> "$MONITOR_LOG_FILE" 2>&1 &
disown

echo "The resilient Celery service monitor has been started in the background."
echo "You can now safely close this terminal. To see the monitor's logs, run:"
echo "tail -f $MONITOR_LOG_FILE"
echo "To see worker/beat logs, run:"
echo "tail -f $WORKER_LOG_FILE"
echo "tail -f $BEAT_LOG_FILE"
