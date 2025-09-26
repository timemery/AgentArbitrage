#!/bin/bash

# This script is designed to be run from the application's root directory.

# Step 1: Kill any lingering Celery worker processes.
# Use sudo to ensure we can kill processes started by any user, including www-data.
echo "Attempting to stop any old Celery workers..."
sudo pkill -f 'celery' || true
sleep 2

# Step 2: Ensure the log file for the Celery worker exists and has correct permissions.
LOG_FILE="/var/www/agentarbitrage/celery.log"
echo "Ensuring log file exists at $LOG_FILE and is owned by www-data..."
sudo touch $LOG_FILE
sudo chown www-data:www-data $LOG_FILE

# Step 3: Start the Celery worker as the www-data user in a detached process.
VENV_PYTHON="/var/www/agentarbitrage/venv/bin/python"
echo "Starting Celery worker as www-data in detached mode..."
sudo -u www-data $VENV_PYTHON -m celery -A celery_config.celery worker --detach --loglevel=DEBUG --logfile=$LOG_FILE

echo "Celery worker startup command issued for user www-data."