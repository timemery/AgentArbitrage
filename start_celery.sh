#!/bin/bash
#
# JULES - TEMPORARY DIAGNOSTIC SCRIPT (V2)
# GOAL: Run the worker in the FOREGROUND as the WWW-DATA user to capture the real error.
#
echo "--- JULES DIAGNOSTIC SCRIPT V2 RUNNING ---"
echo "This script will attempt to start the worker in the foreground as www-data."
echo "Please paste the ENTIRE output, including any errors."
echo "----------------------------------------------------"
sleep 1

# Step 1: Define absolute paths for everything to avoid environment issues.
APP_DIR="/var/www/agentarbitrage"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery worker --beat --loglevel=INFO"

# Step 2: Ensure the directory and its contents are owned by www-data before we start.
# This eliminates permissions as a variable.
echo "Setting ownership of $APP_DIR to www-data..."
chown -R www-data:www-data $APP_DIR

# Step 3: Run the worker command in the foreground as the www-data user.
# NO nohup, NO backgrounding (&), NO log redirection.
echo "Attempting to start the worker as www-data IN THE FOREGROUND..."
su -s /bin/bash -c "cd $APP_DIR && $WORKER_COMMAND" www-data

echo "----------------------------------------------------"
echo "--- DIAGNOSTIC SCRIPT FINISHED ---"
echo "If the script seemed to hang without finishing, that is also useful information."
