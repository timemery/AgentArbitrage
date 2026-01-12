#!/bin/bash

# Clear Celery Logs to reset rejection statistics
# This is useful after a DB reset to ensure "Total Processed" counts are fresh.

LOG_DIR=$(dirname "$0")/..
WORKER_LOG="$LOG_DIR/celery_worker.log"
BEAT_LOG="$LOG_DIR/celery_beat.log"

if [ -f "$WORKER_LOG" ]; then
    echo "Truncating $WORKER_LOG..."
    > "$WORKER_LOG"
else
    echo "Log file $WORKER_LOG not found."
fi

if [ -f "$BEAT_LOG" ]; then
    echo "Truncating $BEAT_LOG..."
    > "$BEAT_LOG"
else
    echo "Log file $BEAT_LOG not found."
fi

echo "Logs cleared. Diagnostic stats should now be 0."
