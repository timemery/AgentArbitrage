#!/bin/bash

# Deployment Script
# Consolidates all steps for updating the application, restarting workers, and triggering data collection.

echo "--- Starting Full Deployment ---"

# Step 1: Fix Permissions
# Critical for ensuring Celery (running as www-data) can read/write DB and logs.
echo "[1/5] Fixing permissions..."
sudo chown -R www-data:www-data /var/www/agentarbitrage

# Step 2: Stop Services
# Kills existing workers and clears stale locks/PIDs.
echo "[2/5] Stopping services..."
./kill_everything_force.sh

# Step 3: Start Services
# Starts Redis, Celery Worker, and Celery Beat monitor.
echo "[3/5] Starting services..."
sudo ./start_celery.sh

# Step 4: Reload Web Server
# Touches the WSGI entry point to force Apache/Flask reload.
echo "[4/5] Reloading Web Server..."
touch wsgi.py

# Step 5: Trigger Backfill
# Initiates the historical data fetch.
echo "[5/5] Triggering Backfill..."
python3 trigger_backfill_task.py

echo "--- Deployment Complete ---"
echo "Monitor logs with: tail -f celery_worker.log"
