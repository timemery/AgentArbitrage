#!/bin/bash

# This script is a minimal, focused test to diagnose the silent failure
# of the Celery worker startup process. It attempts to launch the worker
# as the 'www-data' user and redirects ALL output (stdout and stderr) to a
# dedicated log file, 'test_launch.log', to capture any errors that were
# previously being suppressed.

echo "--- Starting Celery Worker Launch Test ---"

# --- Configuration ---
APP_DIR="/var/www/agentarbitrage"
VENV_PYTHON="$APP_DIR/venv/bin/python"
TEST_LOG_FILE="$APP_DIR/test_launch.log"
WORKER_COMMAND="$VENV_PYTHON -m celery -A worker.celery_app worker --loglevel=INFO --workdir=$APP_DIR"
ENV_SETUP="set -a && source $APP_DIR/.env && set +a"

# --- Test Execution ---
# 1. Clean up any previous test log to ensure a fresh result.
echo "Cleaning up old test log..."
rm -f "$TEST_LOG_FILE"
touch "$TEST_LOG_FILE"
chown www-data:www-data "$TEST_LOG_FILE"

# 2. Attempt to launch the worker. This is the critical command.
#    We use 'su' as it was the last method attempted in the main script.
#    The `> "$TEST_LOG_FILE" 2>&1` is the most important part, as it captures
#    all output, including silent errors.
echo "Attempting to launch Celery worker as www-data..."
echo "All output will be redirected to: $TEST_LOG_FILE"

su -s /bin/bash -c "cd $APP_DIR && $ENV_SETUP && $WORKER_COMMAND" www-data > "$TEST_LOG_FILE" 2>&1

# 3. Final message to the user.
echo "--- Launch Test Finished ---"
echo "The test command has been executed. Please check the contents of the log file:"
echo "cat $TEST_LOG_FILE"
