#!/bin/bash

# Safe Sync Script
# Pulls the latest code from GitHub and runs the deployment process.
# Aborts if you have unsaved local changes to prevent conflicts.

echo "--- Starting Safe Sync ---"

# 1. Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "❌ ERROR: You have uncommitted changes on the server."
    echo "Please run your standard 'push' commands first to save your work:"
    echo "  git add --all"
    echo "  git commit -m '...'"
    echo "  git push origin main"
    echo "Then run this script again."
    exit 1
fi

# 2. Pull from GitHub
echo "[1/2] Pulling latest changes from GitHub..."
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Git pull failed. You might have merge conflicts or network issues."
    exit 1
fi

# 3. Run Deployment
echo "[2/2] Running deployment script..."
sudo ./deploy_update.sh

echo "--- Sync & Deploy Complete ---"
