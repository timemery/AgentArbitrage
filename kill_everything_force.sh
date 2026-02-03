#!/bin/bash
# Updated Feb 3 2026: Fixed order of operations AND added nuclear persistence wipe
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
# We explicitly clear known task locks.
# Adding -h 127.0.0.1 to ensure local connection if binding is restrictive.
redis-cli -h 127.0.0.1 DEL backfill_deals_lock update_recent_deals_lock homogenization_status || echo "Redis soft clear failed (Redis might be down). Proceeding to hard kill."

# Step 4: DYNAMICALLY FIND REDIS DATA DIR (New!)
# Before we kill Redis, let's ask it where it lives.
echo "[4/8] Querying Redis for data directory..."
REDIS_DIR=$(redis-cli -h 127.0.0.1 config get dir | tail -n 1)
REDIS_FILE=$(redis-cli -h 127.0.0.1 config get dbfilename | tail -n 1)

if [ -n "$REDIS_DIR" ] && [ -n "$REDIS_FILE" ]; then
    REDIS_DUMP_PATH="$REDIS_DIR/$REDIS_FILE"
    echo "Identified Redis dump file at: $REDIS_DUMP_PATH"
else
    echo "Could not query Redis config (maybe auth required or down). Will check standard paths."
    REDIS_DUMP_PATH=""
fi

# Step 5: Kill any process listening on the Redis port (6379)
echo "[5/8] Terminating Redis server process..."
sudo fuser -k 6379/tcp || echo "Redis was not running or could not be killed."
sleep 2

# Step 6: NUCLEAR OPTION - Delete Redis Persistence Files
echo "[6/8] Deleting Redis persistence files to prevent zombie lock reload..."

# A. Delete the dynamically found path
if [ -n "$REDIS_DUMP_PATH" ] && [ -f "$REDIS_DUMP_PATH" ]; then
    echo "Deleting dynamic dump path: $REDIS_DUMP_PATH"
    sudo rm -f "$REDIS_DUMP_PATH"
fi

# B. Search common paths (backup)
REDIS_DIRS="/var/lib/redis /etc/redis /var/www/agentarbitrage"
FOUND_DUMP=false

for dir in $REDIS_DIRS; do
    if [ -d "$dir" ]; then
        if sudo find "$dir" -name "dump.rdb" -delete; then
             echo "Deleted dump.rdb in $dir"
             FOUND_DUMP=true
        fi
    fi
done

if [ "$FOUND_DUMP" = false ] && [ ! -f "$REDIS_DUMP_PATH" ]; then
    echo "WARNING: Could not find dump.rdb in standard locations. Searching entire /var/lib..."
    sudo find /var/lib -name "dump.rdb" -delete || echo "No dump.rdb found in /var/lib."
fi

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
