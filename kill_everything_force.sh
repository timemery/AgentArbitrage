#!/bin/bash
echo "--- Starting Forceful Shutdown ---"

# Step 1: Forcefully kill all processes with 'celery' in their command line
echo "[1/5] Forcefully terminating all Celery processes (worker, beat, etc.)..."
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

# Step 2: Kill any process listening on the Redis port (6379)
echo "[2/5] Terminating Redis server..."
sudo fuser -k 6379/tcp || echo "Redis was not running or could not be killed."
sleep 1

# Step 3: Delete the Celery Beat schedule file
echo "[3/5] Deleting Celery Beat schedule file..."
sudo rm -f celerybeat-schedule

# Step 4: Recursively find and delete all __pycache__ directories
echo "[4/5] Deleting all Python cache directories (__pycache__)..."
sudo find . -type d -name "__pycache__" -exec rm -r {} +
echo "Cache cleared."

# Step 5: Restarting Redis server for a clean slate
echo "[5/5] Restarting Redis server..."
sudo service redis-server start

echo "--- Forceful Shutdown Complete ---"
echo "The environment has been forcefully reset. You should now be able to start services cleanly."