#!/bin/bash
# Updated Feb 3 2026 (v3): Implemented "Brain Wipe" (FLUSHALL + SAVE) to guarantee lock removal
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

# Step 3: BRAIN WIPE - Flush All Data from Memory
# This is the most reliable way to clear locks. We wipe memory, then force a save.
echo "[3/8] Executing Redis FLUSHALL (Brain Wipe)..."
redis-cli -h 127.0.0.1 FLUSHALL || echo "Redis FLUSHALL failed (Is Redis running?)."

# Step 4: PERSIST EMPTY STATE - Force Save
# This ensures that when we kill Redis, the file on disk is already empty/clean.
echo "[4/8] Executing Redis SAVE to persist empty state..."
redis-cli -h 127.0.0.1 SAVE || echo "Redis SAVE failed."

# Step 5: Kill any process listening on the Redis port (6379)
echo "[5/8] Terminating Redis server process..."
sudo fuser -k 6379/tcp || echo "Redis was not running or could not be killed."
sleep 2

# Step 6: NUCLEAR OPTION - Delete Redis Persistence Files (Backup Measure)
# We still try to delete the file just in case step 4 failed or Redis panic-saved on death.
echo "[6/8] Deleting Redis persistence files (if any exist) as a backup..."

# Dynamic lookup
REDIS_DIR=$(redis-cli -h 127.0.0.1 config get dir | tail -n 1)
REDIS_FILE=$(redis-cli -h 127.0.0.1 config get dbfilename | tail -n 1)
if [ -n "$REDIS_DIR" ] && [ -n "$REDIS_FILE" ]; then
    REDIS_DUMP_PATH="$REDIS_DIR/$REDIS_FILE"
    if [ -f "$REDIS_DUMP_PATH" ]; then
        echo "Deleting known dump file: $REDIS_DUMP_PATH"
        sudo rm -f "$REDIS_DUMP_PATH"
    fi
fi

# Standard paths backup
REDIS_DIRS="/var/lib/redis /etc/redis /var/www/agentarbitrage"
for dir in $REDIS_DIRS; do
    if [ -d "$dir" ]; then
        sudo find "$dir" -name "dump.rdb" -delete
    fi
done

# Step 7: Delete the Celery Beat schedule file AND PID file
echo "[7/8] Deleting Celery Beat schedule and PID files..."
sudo rm -f celerybeat-schedule
sudo rm -f celerybeat.pid

# Step 8: Recursively find and delete all __pycache__ directories
echo "[8/8] Deleting all Python cache directories (__pycache__)..."
sudo find . -type d -name "__pycache__" -exec rm -r {} +
echo "Cache cleared."

# Step 9: Restarting Redis server for a clean slate
echo "[9/9] Restarting Redis server..."
sudo service redis-server start

echo "--- Forceful Shutdown Complete ---"
echo "The environment has been forcefully reset. You should now be able to start services cleanly."

# Reset terminal to a sane state to fix display issues
stty sane
