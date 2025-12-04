#!/bin/bash

# This script is designed for a production environment.
# It starts the Celery worker and Celery Beat scheduler as separate, resilient daemons.

# Step 1: Set ownership
echo "Ensuring www-data owns the entire application directory..."
chown -R www-data:www-data /var/www/agentarbitrage

# Step 2: Define constants
APP_DIR="/var/www/agentarbitrage"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"

# Define the commands for the worker and scheduler (note: --beat is removed from worker)
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO"
BEAT_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app beat --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app purge -f"

# Step 3: Kill any old Celery processes
echo "Attempting to stop any old Celery processes..."
# A broader pattern to kill both worker and beat processes
pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found."
sleep 2

# Step 4: Purge any waiting tasks
echo "Purging any pending tasks from the message queue..."
su -s /bin/bash -c "cd $APP_DIR && PYTHONPATH=. $PURGE_COMMAND" www-data

# Step 5: Clean up old state and prepare files
echo "Preparing log files and cleaning scheduler state..."
# Forcefully remove the old schedule file to prevent the scheduler from starting in a stale state.
sudo rm -f "$APP_DIR/celerybeat-schedule"
# Ensure both log files exist and have correct permissions
touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"
chown www-data:www-data "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"

# Step 6: Ensure deals.db exists and is writable
echo "Ensuring deals.db exists and is writable..."
touch "$APP_DIR/deals.db"
chown www-data:www-data "$APP_DIR/deals.db"

# Step 7: Start the daemons
# Common environment setup to be used for both processes
ENV_SETUP="cd $APP_DIR && set -a && source .env && set +a && PYTHONPATH=."

# Start the Celery Worker daemon
echo "Starting Celery worker daemon..."
su -s /bin/bash -c "$ENV_SETUP nohup $WORKER_COMMAND >> $WORKER_LOG_FILE 2>&1 &" www-data

# Start the Celery Beat Scheduler daemon
echo "Starting Celery Beat scheduler daemon..."
su -s /bin/bash -c "$ENV_SETUP nohup $BEAT_COMMAND >> $BEAT_LOG_FILE 2>&1 &" www-data

sleep 2
echo "Celery worker and beat scheduler daemons have been started."
echo "You can now monitor their logs independently:"
echo "tail -f $WORKER_LOG_FILE"
echo "tail -f $BEAT_LOG_FILE"
