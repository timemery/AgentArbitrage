#!/bin/bash

# This script is designed to be run from the application's root directory: /var/www/agentarbitrage/

# Step 1: Kill any lingering Celery worker processes to ensure a clean start.
echo "Attempting to stop any old Celery workers..."
pkill -f 'celery -A worker.celery worker'

# It's good practice to wait a moment to let the process die.
sleep 2

# Step 2: Ensure the log file for the Celery worker exists and has correct permissions.
LOG_FILE="/var/www/agentarbitrage/celery.log"
echo "Ensuring log file exists at $LOG_FILE..."
touch $LOG_FILE
echo "Setting ownership of log file to www-data..."
chown www-data:www-data $LOG_FILE

# Step 3: Start the Celery worker as a detached background process.
# We will run this as root, but the --uid and --gid flags will cause
# the worker to drop privileges to the www-data user after starting.
CELERY_COMMAND="/var/www/agentarbitrage/venv/bin/celery"

echo "Starting Celery worker in detached mode as user www-data..."
$CELERY_COMMAND -A worker.celery worker --detach --loglevel=INFO --logfile=$LOG_FILE --uid=www-data --gid=www-data

echo "Celery worker startup command issued."
