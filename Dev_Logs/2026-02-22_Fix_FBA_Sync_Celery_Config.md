# Fix FBA Inventory Sync Issue - Iteration 9

## Overview
The "Sync from Amazon" task was not executing despite the Celery worker being active. Logs confirmed that `smart_ingestor` tasks were running, but the `fetch_existing_inventory_task` was never received by the worker.

## Root Cause Found
**Missing Configuration:** The `keepa_deals.inventory_import` module was **not included** in the `imports` list in `celery_config.py`.
*   Celery workers only register tasks from modules explicitly listed in their configuration or auto-discovered.
*   Because the module wasn't imported at startup, the worker didn't know the `fetch_existing_inventory_task` existed. It silently ignored the messages from the web app.

## Resolution
1.  **Configuration Update:** Added `'keepa_deals.inventory_import'` to the `imports` tuple in `celery_config.py`.
2.  **Logic Confirmed:** The previous fixes (Dual Report fetching, Retry Logic, Parsing Hardening) are all correct and waiting to be executed.

## User Action Required
1.  **Deploy & Restart:** Deploy this change. Your deployment script (`deploy_update.sh`) handles the restart, which is essential for the worker to load the new configuration.
2.  **Run Sync:** Go to the Tracking page and click "Sync from Amazon".
3.  **Verify:** You should now see the task execution in `celery_worker.log` (look for `fetch_existing_inventory_task`), and the database should populate with FBA inventory.
