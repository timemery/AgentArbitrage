#!/bin/bash
set -e

# ==============================================================================
# ==           AGENT ARBITRAGE - DEFINITIVE SOFT RESTART SCRIPT             ==
# ==============================================================================
#
#  This script provides a fully automated, robust restart procedure.
#  It MUST be run as the root user.
#
#  It solves the core environmental issues by:
#    1. Ensuring all file permissions are correct before any other action.
#    2. Using the 'su' command to reliably execute the worker startup logic
#       as the 'www-data' user in a persistent background session.
#
# ==============================================================================

echo "--- [ROOT] Starting Definitive Soft Restart ---"

APP_DIR="/var/www/agentarbitrage"

echo "--> Step 1: Terminating any old Celery or WSGI processes..."
# As root, ensure a clean slate by stopping any lingering processes.
pkill -f 'celery' || true
pkill -f 'wsgi' || true
sleep 2

echo "--> Step 2: Setting correct file ownership for the entire application..."
# This is the critical step that fixes the root cause of previous failures.
cd $APP_DIR
chown -R www-data:www-data .

# Define the full command to be executed as the www-data user.
# This includes cleanup, purging, and the CRITICAL 'nohup ... &' for persistence.
WORKER_STARTUP_COMMAND="
    set -e;
    cd $APP_DIR;
    echo '---> [www-data] Cleaning cache and old schedule file...';
    rm -f celerybeat-schedule;
    find . -type f -name '*.pyc' -delete;
    find . -type d -name '__pycache__' -delete;

    echo '---> [www-data] Purging Celery message queue...';
    ./venv/bin/python -m celery -A worker.celery purge -f;

    echo '---> [www-data] Touching wsgi.py to reload web server...';
    touch wsgi.py;

    echo '---> [www-data] Starting new Celery worker in the background...';
    touch celery.log;
    nohup ./venv/bin/python -m celery -A worker.celery worker --loglevel=INFO --beat >> celery.log 2>&1 &
"

echo "--> Step 3: Executing worker startup process as www-data user..."
# Use 'su' to switch to the www-data user and execute the entire startup
# command string in a new shell. This is the most reliable method.
su -s /bin/bash -c "$WORKER_STARTUP_COMMAND" www-data

echo ""
echo "--- [ROOT] System restart commands have been issued. ---"
echo "The Celery worker should now be running as www-data."
echo "You can monitor its progress with: tail -f $APP_DIR/celery.log"
