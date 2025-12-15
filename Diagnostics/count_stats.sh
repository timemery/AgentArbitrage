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
    echo "Warning: Log file '$LOG_PATH' not found. Stats will be incomplete."
    REJECTED_COUNT=0
    REASON_NO_OFFER=0
    REASON_LIST_AT=0
    REASON_1YR_AVG=0
else
    # Count specific rejection reasons
    REASON_NO_OFFER=$(grep -c "No used offer found" "$LOG_PATH")
    REASON_LIST_AT=$(grep -c "Excluding deal because 'List at' is missing" "$LOG_PATH")
    REASON_1YR_AVG=$(grep -c "Excluding deal because '1yr. Avg.' is missing" "$LOG_PATH")

    # Total Rejected
    REJECTED_COUNT=$((REASON_NO_OFFER + REASON_LIST_AT + REASON_1YR_AVG))
fi

# Count DB rows using Python (more portable if sqlite3 CLI is missing)
DB_COUNT=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_PATH'); cursor=conn.cursor(); cursor.execute('SELECT COUNT(*) FROM deals'); print(cursor.fetchone()[0])")

# Calculate Total Processed
TOTAL=$((DB_COUNT + REJECTED_COUNT))

# Output
echo "========================================"
echo "          DEAL PROCESSING STATS         "
echo "========================================"
echo "Total Processed:       $TOTAL"
echo "Successfully Saved:    $DB_COUNT"
echo "Total Rejected:        $REJECTED_COUNT"

if [ $TOTAL -gt 0 ]; then
    PERCENT=$(awk "BEGIN {printf \"%.2f\", ($REJECTED_COUNT/$TOTAL)*100}")
    echo "Rejection Rate:        $PERCENT%"
fi

echo ""
echo "--- Rejection Breakdown ---"
if [ $REJECTED_COUNT -gt 0 ]; then
    # Calculate breakdown percentages
    P_NO_OFFER=$(awk "BEGIN {printf \"%.1f\", ($REASON_NO_OFFER/$REJECTED_COUNT)*100}")
    P_LIST_AT=$(awk "BEGIN {printf \"%.1f\", ($REASON_LIST_AT/$REJECTED_COUNT)*100}")
    P_1YR_AVG=$(awk "BEGIN {printf \"%.1f\", ($REASON_1YR_AVG/$REJECTED_COUNT)*100}")

    echo "1. No Used Offer Found:  $REASON_NO_OFFER ($P_NO_OFFER%)"
    echo "   (Deal has no valid used offers to analyze)"
    echo ""
    echo "2. Missing 'List at':    $REASON_LIST_AT ($P_LIST_AT%)"
    echo "   (Could not determine a safe listing price or AI rejected it)"
    echo ""
    echo "3. Missing '1yr Avg':    $REASON_1YR_AVG ($P_1YR_AVG%)"
    echo "   (Insufficient sales history/data points)"
else
    echo "No rejections found."
fi
echo "========================================"
