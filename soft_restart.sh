#!/bin/bash
set -e

echo "--- BEGINNING SOFT SYSTEM RESTART ---"

echo "--> Step 1: Stopping all services..."
sudo pkill -f 'celery' || true
sudo systemctl stop apache2 || true
sudo pkill -f 'apache2|wsgi' || true
sleep 2

echo "--> Step 2: Setting correct file permissions..."
# Ensure the script is run from the project root for chown to work as expected
cd /var/www/agentarbitrage
sudo chown -R www-data:www-data .

echo "--> Step 3: Cleaning Python cache..."
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete

echo "--> Step 4: Starting services..."
sudo systemctl start redis-server
echo "--> Waiting for Redis to initialize..."
sleep 2 # CRITICAL: Give Redis a moment to start before trying to connect.

# Define variables
VENV_PYTHON="/var/www/agentarbitrage/venv/bin/python"
LOG_FILE="/var/www/agentarbitrage/celery.log"
APP_DIR="/var/www/agentarbitrage"

# --- NEW CRITICAL STEP: Purge the Celery message queue ---
echo "--> Step 4a: Purging any old tasks from the message queue..."
# Added '|| true' to make this step resilient. If it fails, the script will continue.
sudo -u www-data sh -c "cd $APP_DIR && $VENV_PYTHON -m celery -A worker.celery purge -f" || true

echo "--> Step 4b: Restarting web server..."
# Touch the wsgi.py file to gracefully reload the application in Apache/mod_wsgi
touch $APP_DIR/wsgi.py
sudo systemctl start apache2

echo "--> Step 4c: Starting new Celery worker in the background..."
# Ensure the log file exists and has the correct permissions
sudo touch $LOG_FILE
sudo chown www-data:www-data $LOG_FILE

# Start the worker as the www-data user
sudo -u www-data sh -c "cd $APP_DIR && nohup $VENV_PYTHON -m celery -A worker.celery worker --loglevel=INFO --beat >> $LOG_FILE 2>&1 &"

echo ""
echo "--- SYSTEM RESTART COMMANDS ISSUED ---"
echo "Please wait ~15 seconds for the worker to start."
echo "You can monitor its progress with: tail -f /var/www/agentarbitrage/celery.log"
