#!/bin/bash

# Define paths (adjust if running from a different directory)
DB_PATH="deals.db"
LOG_PATH="celery_worker.log"

# Check if DB exists
if [ ! -f "$DB_PATH" ]; then
    # Try alternate location
    if [ -f "data/deals.db" ]; then
        DB_PATH="data/deals.db"
    elif [ -f "../deals.db" ]; then
        DB_PATH="../deals.db"
    else
        echo "Error: Database file 'deals.db' not found in current or standard directories."
        echo "Please run this script from the project root."
        exit 1
    fi
fi

# Check if log exists
if [ ! -f "$LOG_PATH" ]; then
    echo "Warning: Log file '$LOG_PATH' not found. Rejected count will be 0."
    REJECTED_COUNT=0
else
    # Count rejections
    # We look for:
    # "Excluding deal" (covers List at missing, 1yr Avg missing)
    # "No used offer found" (covers no valid used offer)
    REJECTED_COUNT=$(grep -c -E "Excluding deal|No used offer found" "$LOG_PATH")
fi

# Count DB rows using Python (more portable if sqlite3 CLI is missing)
DB_COUNT=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_PATH'); cursor=conn.cursor(); cursor.execute('SELECT COUNT(*) FROM deals'); print(cursor.fetchone()[0])")

# Calculate Total
TOTAL=$((DB_COUNT + REJECTED_COUNT))

# Output
echo "Total processed:   $TOTAL"
echo "Rejected deals:    $REJECTED_COUNT"
echo "Total deals in db: $DB_COUNT"

# Optional: Calculate percentage
if [ $TOTAL -gt 0 ]; then
    PERCENT=$(awk "BEGIN {printf \"%.2f\", ($REJECTED_COUNT/$TOTAL)*100}")
    echo "Rejection Rate:    $PERCENT%"
fi
