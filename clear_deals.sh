#!/bin/bash
# clear_deals.sh
# A convenience script to clear old deal data and user restrictions
# without interacting with user credentials or inventory tables.

echo "Clearing old deals data from the database..."
python3 Diagnostics/reset_database.py --force

echo ""
echo "Data cleared. If you wish to restart the ingestor loop immediately,"
echo "you can restart the celery worker (e.g. via ./deploy_update.sh or ./start_celery.sh)."
