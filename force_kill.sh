#!/bin/bash
#
# force_kill.sh
# An aggressive script to find and terminate all running Celery processes.
# This uses `kill -9` and should be used when standard restarts are failing.

echo "Searching for running Celery processes..."

# Find PIDs of all processes with 'celery' in their command, excluding the grep process itself.
# This will find processes run by any user.
PIDS=$(ps aux | grep 'celery' | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
  echo "No running Celery processes found."
else
  echo "Found the following Celery process PIDs: $PIDS"
  echo "Attempting to terminate with 'sudo kill -9'..."

  # Use sudo to ensure we have permission to kill processes owned by any user (e.g., www-data).
  # The PIDS variable is intentionally not in quotes to allow word splitting.
  sudo kill -9 $PIDS

  echo "Kill command sent."

  # Verify that the processes are gone
  sleep 2
  echo "Verifying that processes were terminated..."
  POST_KILL_PIDS=$(ps aux | grep 'celery' | grep -v grep | awk '{print $2}')

  if [ -z "$POST_KILL_PIDS" ]; then
    echo "SUCCESS: All found Celery processes have been terminated."
  else
    echo "WARNING: The following Celery processes could NOT be terminated: $POST_KILL_PIDS"
    echo "You may need to run this script again or intervene manually."
  fi
fi
