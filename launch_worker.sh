#!/bin/bash

# This script is designed to be executed by start_celery.sh as the www-data user.
# It sets up the environment and launches the Celery worker.

# Define constants
APP_DIR="/var/www/agentarbitrage"
VENV_PYTHON="$APP_DIR/venv/bin/python"
WORKER_LOG_FILE="$APP_DIR/celery_worker.log"
DIAG_LOG_FILE="$APP_DIR/diag_startup.log"

# --- Step 1: Set up Environment ---
# Change to the application directory. This is critical.
cd "$APP_DIR" || exit 1

# Source environment variables from .env
set -a
if [ -f .env ]; then
  source .env
fi
set +a

# --- Step 2: Run Diagnostics ---
# Log critical environment details to a diagnostic file.
echo "--- DIAGNOSTIC START ---" >> "$DIAG_LOG_FILE"
date >> "$DIAG_LOG_FILE"
echo "User: $(whoami)" >> "$DIAG_LOG_FILE"
echo "Current Directory: $(pwd)" >> "$DIAG_LOG_FILE"
echo "Python Executable being used: $(which python3)" >> "$DIAG_LOG_FILE"
echo "VENV Python Executable specified in script: $VENV_PYTHON" >> "$DIAG_LOG_FILE"
echo "PYTHONPATH: $PYTHONPATH" >> "$DIAG_LOG_FILE"
echo "--- DIAGNOSTIC END ---" >> "$DIAG_LOG_FILE"

# --- Step 3: Define and Launch Worker ---
# The --workdir flag is used for maximum robustness.
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO --workdir=$APP_DIR"

# Launch the worker in the background using nohup.
# The output is redirected to the worker log.
nohup $WORKER_COMMAND >> "$WORKER_LOG_FILE" 2>&1 &
