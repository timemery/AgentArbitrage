#!/bin/bash

# Safe Sync Script (Version 2.0)
# Pulls the latest code from GitHub and runs the deployment process.
# Usage: ./sync_from_repo.sh [--reset]

echo "--- Starting Safe Sync ---"

FORCE_RESET=0

# Parse arguments
if [[ "$1" == "--reset" ]]; then
    FORCE_RESET=1
    echo "⚠️  WARNING: Reset mode enabled. Discarding ALL local changes..."
fi

# 1. Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    if [ $FORCE_RESET -eq 1 ]; then
        echo "Running 'git reset --hard HEAD' to discard local changes..."
        git reset --hard HEAD
    else
        echo "❌ ERROR: You have uncommitted changes on the server."
        echo "To keep your changes, commit/push them first:"
        echo "  git add . && git commit -m 'Save work' && git push origin main"
        echo ""
        echo "To DISCARD your changes and force update:"
        echo "  ./sync_from_repo.sh --reset"
        exit 1
    fi
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
