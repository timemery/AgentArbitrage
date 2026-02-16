#!/bin/bash

echo "Optimizing VPS Resources..."

# Stop and Disable MySQL (as requested by Host)
echo "Attempting to stop MySQL/MariaDB..."
sudo systemctl stop mysql 2>/dev/null
sudo systemctl disable mysql 2>/dev/null
sudo systemctl stop mariadb 2>/dev/null
sudo systemctl disable mariadb 2>/dev/null

echo "Optimization complete: Database service stopped."
