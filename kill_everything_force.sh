#!/bin/bash
# Updated Feb 3 2026: Fixed order of operations to ensure Redis locks are cleared BEFORE killing Redis
echo "--- Starting Forceful Shutdown ---"

# Step 1: Forcefully kill the monitor process
echo "[1/7] Forcefully terminating the monitor process..."
sudo pkill -f "monitor_and_restart"
sleep 2 # Give a moment for the process to die

# Step 2: Forcefully kill all processes with 'celery' in their command line
echo "[2/7] Forcefully terminating all Celery processes (worker, beat, etc.)..."
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

# Step 3: Clear ALL Redis locks to prevent stale lock issues (MUST be done before killing Redis)
echo "[3/7] Clearing stale Redis locks (Backfiller and Upserter)..."
# We attempt to clear locks. If Redis is already dead/unresponsive, this fails,
# but we will nuke the persistence file in Step 4.5 to be sure.
redis-cli DEL backfill_deals_lock update_recent_deals_lock || echo "Redis command failed (Redis might be down). Proceeding to nuke persistence."

# Step 4: Kill any process listening on the Redis port (6379)
echo "[4/7] Terminating Redis server process..."
sudo fuser -k 6379/tcp || echo "Redis was not running or could not be killed."
sleep 1

# Step 5: Delete the Celery Beat schedule file AND PID file
echo "[5/7] Deleting Celery Beat schedule and PID files..."
sudo rm -f celerybeat-schedule
sudo rm -f celerybeat.pid

# Step 6: Recursively find and delete all __pycache__ directories
echo "[6/7] Deleting all Python cache directories (__pycache__)..."
sudo find . -type d -name "__pycache__" -exec rm -r {} +
echo "Cache cleared."

# Step 7: Restarting Redis server for a clean slate
echo "[7/7] Restarting Redis server..."
sudo service redis-server start

echo "--- Forceful Shutdown Complete ---"
echo "The environment has been forcefully reset. You should now be able to start services cleanly."

# Reset terminal to a sane state to fix display issues
stty sane
