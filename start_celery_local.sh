#!/bin/bash
# A simplified, sandbox-safe script to start Celery services.

# Kill any old processes to ensure a clean start
echo "Stopping old Celery and Redis processes..."
pkill -f "celery -A worker.celery_app" || echo "No old Celery processes found."
pkill -f "redis-server" || echo "No old Redis process found."
sleep 2

# Start Redis
echo "Starting Redis server..."
redis-server >/dev/null 2>&1 &
sleep 5 # Give Redis more time to start

# Check if Redis started
redis-cli ping
if [ $? -ne 0 ]; then
    echo "Redis failed to start. Aborting."
    exit 1
fi
echo "Redis started successfully."

# Define constants
APP_DIR="$(pwd)"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
BEAT_LOG_FILE="$APP_DIR/celery_beat.log"

# Define the commands
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO --workdir=$APP_DIR"
BEAT_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app beat --loglevel=INFO --workdir=$APP_DIR"
ENV_SETUP="set -a && source .env && set +a" # .env is now sourced relative to the new CWD

# Clean up state
echo "Cleaning up old state..."
rm -f "$APP_DIR/celerybeat-schedule"
touch "$WORKER_LOG_FILE" "$BEAT_LOG_FILE"

# Start Celery Worker and Beat using the corrected sudo command with an explicit cd
echo "Starting Celery worker..."
sudo -u www-data bash -c "cd $APP_DIR && $ENV_SETUP && $WORKER_COMMAND" >> "$WORKER_LOG_FILE" 2>&1 &

echo "Starting Celery beat..."
sudo -u www-data bash -c "cd $APP_DIR && $ENV_SETUP && $BEAT_COMMAND" >> "$BEAT_LOG_FILE" 2>&1 &

echo "Services started. Check celery_worker.log and celery_beat.log for status."
