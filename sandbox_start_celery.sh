#!/bin/bash
# A sandbox-friendly script to start the Celery worker in the background.

# Define paths and commands
APP_DIR=$(pwd)
LOG_FILE="$APP_DIR/celery.log"
VENV_PYTHON="python3"
# CRITICAL: Point to the new celery_app object in worker.py
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --beat --loglevel=INFO"
PURGE_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app purge -f"

# Stop any old workers
echo "Stopping any old Celery workers..."
pkill -f "celery -A worker" || true
sleep 2

# Purge the queue
echo "Purging task queue..."
$PURGE_COMMAND

# Clean up old log and schedule files for a fresh start
echo "Cleaning up old log and schedule files..."
rm -f $LOG_FILE
rm -f $APP_DIR/celerybeat-schedule
touch $LOG_FILE

# Start the new worker in the background
echo "Starting Celery worker in the background..."
nohup $WORKER_COMMAND >> $LOG_FILE 2>&1 &

sleep 2
echo "Celery worker has been started. Check celery.log for status."
