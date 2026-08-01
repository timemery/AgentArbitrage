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

# Step 2.5: Force Clear Locks (Safety Net)
# Explicitly removes lock keys in case the full wipe failed or was skipped.
echo "[2.5/5] Ensuring locks are cleared..."
APP_DIR=$(pwd)
if [ -f "$APP_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$APP_DIR/venv/bin/python"
elif [ -f "$APP_DIR/venv/bin/python3" ]; then
    VENV_PYTHON="$APP_DIR/venv/bin/python3"
else
    VENV_PYTHON="python3"
fi
$VENV_PYTHON Diagnostics/force_clear_locks.py

# Step 2.6: Force Pause (Recharge Mode)
# CRITICAL: DO NOT REMOVE. This prevents "Livelock" where the system
# restarts with low tokens (e.g. 40) and never enters the efficient Burst Cycle.
# It forces a full recharge (to 280) before processing begins.
echo "[2.6/5] Forcing Recharge Mode (Pause until Refill)..."
$VENV_PYTHON Diagnostics/force_pause.py

# Step 3: Start Services
# Starts Redis, Celery Worker, and Celery Beat monitor.
echo "[3/5] Starting services..."
sudo ./start_celery.sh

# Step 4: Reload Web Server and Apply Apache Configuration
echo "[4/5] Reloading Web Server & Applying Apache Configuration..."
if [ -d "/etc/apache2/sites-available" ]; then
    echo "Copying agentarbitrage.conf to /etc/apache2/sites-available/..."
    sudo cp agentarbitrage.conf /etc/apache2/sites-available/agentarbitrage.conf

    # If sites-enabled/agentarbitrage.conf is a real file (not a symlink), remove it to allow proper linking
    if [ -f "/etc/apache2/sites-enabled/agentarbitrage.conf" ] && [ ! -L "/etc/apache2/sites-enabled/agentarbitrage.conf" ]; then
        echo "Removing duplicate real file in /etc/apache2/sites-enabled/ to allow proper symbolic linking..."
        sudo rm -f /etc/apache2/sites-enabled/agentarbitrage.conf
    fi

    echo "Enabling Apache site configuration..."
    sudo a2ensite agentarbitrage.conf
fi
echo "Restarting Apache web server..."
sudo systemctl restart apache2 || sudo service apache2 restart || echo "Warning: Could not restart Apache service."
touch wsgi.py

# Step 5: Trigger Backfill (Removed)
# Smart Ingestor starts automatically via Celery Beat (every minute).
echo "[5/5] Data Collection (Smart Ingestor) will start automatically via Celery Beat."

echo "--- Deployment Complete ---"
echo "Monitor logs with: tail -f celery_worker.log"
