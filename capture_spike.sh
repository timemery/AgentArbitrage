#!/bin/bash

# Calculate seconds until the next 55-second mark
current_sec=$(date +%S)
if [ $current_sec -lt 55 ]; then
    sleep_seconds=$((55 - current_sec))
else
    sleep_seconds=$((60 - current_sec + 55))
fi

echo "Waiting $sleep_seconds seconds for the top of the minute ingest window..."
sleep $sleep_seconds

echo "Capturing 20-second snapshot across the minute boundary..."
echo "Starting at: $(date -u +%H:%M:%S)"

# Run the host's requested diagnostic command
for i in {1..20}; do
    date -u +%H:%M:%S
    ps -eo pid,cmd,%cpu,%mem --sort=-%cpu | head -n 12
    sleep 1
    echo "----"
done > spike_log.txt

echo "Capture complete. Results saved to spike_log.txt"
