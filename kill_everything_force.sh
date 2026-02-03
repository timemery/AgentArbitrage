#!/bin/bash
# Updated Feb 3 2026: Fixed order of operations AND added targeted nuclear persistence wipe
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

# Step 3: Clear ALL Redis locks (Soft Clear)
echo "[3/8] Attempting to clear Redis locks via CLI..."
# We attempt to clear locks. If Redis is already dead/unresponsive, this might fail.
redis-cli DEL backfill_deals_lock update_recent_deals_lock || echo "Redis soft clear failed. Proceeding to hard kill."

# Step 4: Kill any process listening on the Redis port (6379)
echo "[4/8] Terminating Redis server process..."
sudo fuser -k 6379/tcp || echo "Redis was not running or could not be killed."
sleep 2

# Step 5: NUCLEAR OPTION - Delete Redis Persistence Files
# This ensures that even if Step 3 failed, the locks cannot reload from disk on restart.
# We target the files explicitly found on the user's server.
echo "[5/8] Deleting Redis persistence files (dump.rdb) to prevent zombie lock reload..."
sudo rm -f /var/lib/redis/dump.rdb
sudo rm -f /var/www/agentarbitrage/dump.rdb
echo "Redis persistence files deleted (if they existed)."

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
