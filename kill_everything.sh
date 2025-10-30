#!/bin/bash
# This script is designed to forcefully stop all potentially interfering processes
# and clear temporary caches without deleting any critical data.

echo "--- Stopping all Celery and Redis processes ---"
sudo pkill -9 -f celery
sudo pkill -9 -f redis-server
sudo pkill -9 -f redis # A more general pattern to catch any redis process

echo "--- Removing Celery Beat schedule file ---"
sudo rm -f celerybeat-schedule

echo "--- Clearing all Python caches ---"
find . -type d -name "__pycache__" -exec rm -r {} +

echo "--- Checking for open file handles on deals.db ---"
lsof deals.db || echo "No open file handles on deals.db"

echo "--- Restarting Redis server in the background ---"
sudo redis-server &
sleep 2 # Give Redis a moment to start up

echo "--- Optional, more aggressive cleaning (commented out) ---"
# The following commands are for more extreme situations, like data corruption.
# Use with caution.

# echo "--- Deleting Redis persistence file (use if Redis fails to start) ---"
# sudo rm -f /var/lib/redis/dump.rdb
# sudo rm -f /var/lib/redis/appendonly.aof

# echo "--- Deleting application log files ---"
# sudo rm -f *.log

echo "--- Kill everything script finished ---"
