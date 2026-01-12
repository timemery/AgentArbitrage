# Dev Log: Fix Rejection Rate & Remove Best Price

**Date:** 2026-01-12
**Author:** Jules (AI Agent)
**Status:** Successful
**Related Files:** `keepa_deals/field_mappings.py`, `keepa_deals/headers.json`, `keepa_deals/processing.py`, `keepa_deals/recalculator.py`, `templates/dashboard.html`

## Task Overview
The primary objective was to investigate an excessively high deal rejection rate (~91%) and a corresponding "slow leak" where the total number of deals in the dashboard was decreasing over time. A secondary objective, added during the session, was to remove the deprecated "Best Price" field and replace it with "Price Now" to reduce confusion and technical debt.

## Investigation & Root Cause

1.  **The "Slow Leak" Mechanism:**
    -   The system relies on a "Mark and Sweep" garbage collection strategy.
    -   **Mark:** The Backfiller/Refiller updates the `last_seen_utc` timestamp when it successfully processes a deal.
    -   **Sweep:** The "Janitor" task deletes deals with timestamps older than 72 hours.
    -   **Failure:** Because valid deals were being erroneously rejected during processing, their timestamps were never updated. The Janitor correctly identified them as "stale" (untouched for >72h) and deleted them, causing the database to drain.

2.  **The Rejection Bug:**
    -   Logs indicated 100% of rejections were due to "Missing 'List at'".
    -   Reproduction scripts confirmed that even for high-quality deals (e.g., "Campbell Biology") where xAI approved the price, the system claimed `List at` was missing.
    -   **Root Cause:** A critical **Column Alignment Mismatch**.
        -   `keepa_deals/headers.json` defined **247** columns.
        -   `keepa_deals/field_mappings.py` defined only **245** function mappings.
        -   The mismatch (missing `Offers 180` and `Offers 365`) caused a shift in the data extraction loop. The function to extract `List at` was being applied to the wrong column index (likely `Trough Season` or similar), resulting in `None` or invalid data.

## Actions Taken

1.  **Fixed Column Alignment:**
    -   Identified the missing entries in `field_mappings.py`.
    -   Inserted `None` placeholders for `Offers 180` and `Offers 365` to restore synchronization between headers and functions.

2.  **Removed "Best Price":**
    -   Removed "Best Price" from `headers.json` and `field_mappings.py`.
    -   Updated `processing.py` to stop populating `row_data['Best Price']`.
    -   Refactored `recalculator.py` to map the database column `"Price Now"` to the internal key `"Now"`, replacing the old dependency on `"Best Price"`.

3.  **Frontend Updates:**
    -   Modified `templates/dashboard.html` to display the `Price_Now` column instead of `Best_Price`.
    -   Updated the "Deal Details Overlay" to bind to `deal.Price_Now`.

4.  **Verification:**
    -   **Backend:** Created `verify_fix.py` which processed a known valid ASIN (`0134093410`). Confirmed that `List at` was correctly populated ($28.39) and the deal was **Saved** instead of Rejected.
    -   **Alignment:** Verified `headers.json` and `field_mappings.py` counts now match perfectly (246 items after removal/fix).
    -   **Frontend:** Used Playwright to verify the dashboard loads and displays the "Buy For" column correctly using the new data source.

## Outcome
The task was **Successful**.
-   The column alignment bug is fixed, which should immediately resolve the high rejection rate and stop the "slow leak" of deals.
-   The redundant "Best Price" field has been successfully removed, simplifying the data model.
