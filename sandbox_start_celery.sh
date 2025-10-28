#!/bin/bash
APP_DIR="."
LOG_FILE="$APP_DIR/celery.log"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --beat --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery purge -f"

echo "Attempting to stop any old Celery workers..."
pkill -f "celery -A worker.celery" || true
sleep 2

echo "Purging any pending tasks from the Celery queue..."
$PURGE_COMMAND

echo "Ensuring log file exists at $LOG_FILE..."
rm -f $LOG_FILE
rm -f $APP_DIR/celerybeat-schedule
touch $LOG_FILE

echo "Starting Celery worker in the background, logging to $LOG_FILE..."
nohup $WORKER_COMMAND >> $LOG_FILE 2>&1 &
sleep 2
echo "Celery worker startup command has been issued. Check status with 'ps aux | grep celery'."
