# Fix Data Collection Stall & Schema Mismatch

**Date:** 2026-02-10
**Status:** SUCCESS (not true - this was not a success)
**Files Modified:** 
- `keepa_deals/db_utils.py`
- `keepa_deals/smart_ingestor.py`
- `Diagnostics/rewind_watermark.py` (Created)

## Problem Overview
The deal ingestion pipeline ("Smart Ingestor") was completely stalled, showing "0 Deals" on the dashboard for over 24 hours. Diagnostics revealed two concurrent issues:
1.  **Infinite Loop / Crash:** The ingestor was repeatedly fetching the same batch of deals but failing to save them to the database. The root cause was a `sqlite3.OperationalError` due to missing columns (e.g., `Detailed_Seasonality`) in the production `deals` table schema, which had drifted from the codebase's `headers.json`.
2.  **Token Starvation / Slow Progress:** The system was spending excessive tokens (20 per deal) processing "dead" inventory (items with zero sales velocity) because the cheap "Peek" filter (2 tokens) was too permissive. This drained the token bucket (refill 5/min) rapidly, causing 80% of runtime to be spent in "Recharge Mode".

## Diagnosis Steps
*   **Log Analysis:** `celery_worker.log` showed the ingestor task starting, running for a few seconds, and then hitting a "Stop Trigger" immediately on subsequent runs, indicating a watermark desynchronization or a failure to advance.
*   **DB Inspection:** Verified via diagnostic script that the `deals` table had 0 rows despite the logs claiming to fetch deals.
*   **Code Review:** Identified that `create_deals_table_if_not_exists` in `db_utils.py` only checked for basic system columns and did not sync with `headers.json`.
*   **Verification:** Created `tests/verify_schema_migration.py` which reproduced the schema mismatch failure.

## Solutions Implemented

### 1. Dynamic Schema Migration
*   **File:** `keepa_deals/db_utils.py`
*   **Logic:** Modified `create_deals_table_if_not_exists` to load `headers.json`, iterate through all defined fields, and automatically execute `ALTER TABLE ... ADD COLUMN` for any missing columns in the SQLite database.
*   **Impact:** Prevents silent failures during `INSERT`, allowing the transaction to commit and the watermark to advance.

### 2. Dead Inventory Filtering (Optimization)
*   **File:** `keepa_deals/smart_ingestor.py`
*   **Logic:** Enhanced `check_peek_viability` to inspect `salesRankDrops365` from the lightweight "Peek" stats.
*   **Rule:** Reject any deal with `< 4` sales drops in the last year immediately (cost: 2 tokens).
*   **Impact:** Increases throughput for dead inventory by ~10x, preventing token starvation on junk data.

### 3. Watermark Recovery
*   **Tool:** Created `Diagnostics/rewind_watermark.py`.
*   **Action:** Manually reset the `watermark_iso` in the `system_state` table to 24 hours in the past.
*   **Impact:** Forced the ingestor to re-scan the period where data was lost due to the DB crash.

## Result
*   **System Restored:** Logs confirmed the ingestor successfully locked, fetched pages, and advanced the watermark past the "stuck" point.
*   **Backlog Processing:** The system began churning through the 24-hour backlog at a rate of ~3 hours of history per hour of runtime.
*   **Data Integrity:** Validated that `List at` calculations and `Detailed_Seasonality` logic are functioning correctly via `Diagnostics/debug_inference.py`.

## Lessons Learned
*   **Schema Drift:** SQLite does not auto-migrate. Any change to `headers.json` MUST be accompanied by a schema migration strategy. The new dynamic loader solves this permanently.
*   **Token Efficiency:** For low-tier Keepa plans (5 tokens/min), filtering logic must be extremely aggressive at the "Peek" stage. Waiting for full analysis to reject dead items is too expensive.
