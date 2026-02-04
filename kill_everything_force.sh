#!/bin/bash
# Updated Feb 3 2026 (v4): Replaced brittle redis-cli with robust Python script
echo "--- Starting Forceful Shutdown ---"

# Step 1: Forcefully kill the monitor process
echo "[1/8] Forcefully terminating the monitor process..."
sudo pkill -f "monitor_and_restart"
sleep 2 # Give a moment for the process to die

# Step 2: Forcefully kill all processes with 'celery' in their command line
echo "[2/8] Forcefully terminating all Celery processes (worker, beat, etc.)..."
sudo pkill -9 -f celery
sleep 2 # Give a moment for processes to die

# Double-check if any Celery processes survived
if pgrep -f celery > /dev/null
then
    echo "WARNING: Some Celery processes survived the first kill. Attempting again..."
    sudo pkill -9 -f celery
else
    echo "All Celery processes terminated successfully."
fi

# Step 3: BRAIN WIPE - Python Execution
# We use the app's python environment to ensure we have the correct credentials/library to wipe Redis.
echo "[3/8] Executing Python-based Redis Wipe..."

APP_DIR=$(pwd)
# Dynamic Python Path Logic
if [ -f "$APP_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$APP_DIR/venv/bin/python"
elif [ -f "$APP_DIR/venv/bin/python3" ]; then
    VENV_PYTHON="$APP_DIR/venv/bin/python3"
else
    VENV_PYTHON="python3"
fi

SCRIPT_PATH="$APP_DIR/Diagnostics/kill_redis_safely.py"

if [ -f "$SCRIPT_PATH" ]; then
    if [[ "$VENV_PYTHON" == "python3" ]]; then
        $VENV_PYTHON $SCRIPT_PATH || echo "Python wipe script failed."
    else
        sudo $VENV_PYTHON $SCRIPT_PATH || echo "Python wipe script failed."
    fi
else
    echo "Warning: Python wipe script not found at $SCRIPT_PATH. Falling back to redis-cli."
    redis-cli -h 127.0.0.1 FLUSHALL || echo "Redis FLUSHALL failed."
    redis-cli -h 127.0.0.1 SAVE || echo "Redis SAVE failed."
fi

# Step 4: Kill any process listening on the Redis port (6379)
echo "[4/8] Terminating Redis server process..."
sudo fuser -k 6379/tcp || echo "Redis was not running or could not be killed."
sleep 2

# Step 5: NUCLEAR OPTION - Delete Redis Persistence Files (Backup Measure)
echo "[5/8] Deleting Redis persistence files (if any exist) as a backup..."

# Dynamic lookup via Python output could be parsed, but simpler to rely on the Python script's success.
# We retain the standard path sweep just in case.
REDIS_DIRS="/var/lib/redis /etc/redis /var/www/agentarbitrage"
for dir in $REDIS_DIRS; do
    if [ -d "$dir" ]; then
        sudo find "$dir" -name "dump.rdb" -delete
    fi
done

# Step 6: Delete the Celery Beat schedule file AND PID file
echo "[6/8] Deleting Celery Beat schedule and PID files..."
sudo rm -f celerybeat-schedule
sudo rm -f celerybeat.pid

# Step 7: Recursively find and delete all __pycache__ directories
echo "[7/8] Deleting all Python cache directories (__pycache__)..."
sudo find . -type d -name "__pycache__" -exec rm -r {} +
echo "Cache cleared."

# Step 8: Restarting Redis server for a clean slate
echo "[8/8] Restarting Redis server..."
sudo service redis-server start

echo "--- Forceful Shutdown Complete ---"
echo "The environment has been forcefully reset. You should now be able to start services cleanly."

# Reset terminal to a sane state to fix display issues
stty sane
