# Fix Dashboard Bad Data Filtering (2026-02-07)

## Problem
The user reported "missing data" on the dashboard (e.g., `1yr Avg` as `-`) and deals with zero or negative profit appearing, despite previous efforts to prevent this.
Inspection revealed that while ingestion logic had some checks, the dashboard API (`/api/deals`) was not strictly enforcing these constraints, allowing legacy or "zombie" data to leak through.

## References to Previous Work
*   **Dev_Log 9:** Mentioned the goal of "strictly excluding incomplete or invalid deals" to improve data quality.
*   **2026-02-04 Log:** Discussed backend column sanitization but didn't explicitly detail the global filtering strategy.

## Solution
We implemented a multi-layered defense to permanently solve this:

1.  **Global API Filtering (`wsgi_handler.py`):**
    *   The `/api/deals` endpoint now enforces strict global filters regardless of user selection:
        *   `Profit > 0` (unless explicitly querying for losses, which is not exposed in UI).
        *   `List_at > 0` and `IS NOT NULL`.
        *   `1yr_Avg` is valid (not NULL, not `-`, not `N/A`, not `0`).
    *   This ensures that even if bad data exists in the DB (legacy), it will never be served to the frontend.

2.  **Ingestion Integrity (`keepa_deals/processing.py`):**
    *   Updated `clean_numeric_values` to include `"Avg"` keyword. This ensures `1yr. Avg.` is stored as a REAL number (float) instead of a raw string, enabling proper sorting and filtering in the future.
    *   (Existing logic in `backfiller.py` already rejects negative profit deals during ingestion, but this adds a second layer).

3.  **Database Cleanup (Planned):**
    *   A purge script is available (`Diagnostics/purge_zombie_deals.py`) to remove existing bad records, but the API filter is the primary protection.

## Verification
*   Checked `deals.db` schema to confirm column names (`1yr_Avg`, `List_at`).
*   Verified that `clean_numeric_values` now correctly parses `1yr. Avg.` strings into floats.
*   Verified that `/api/deals` adds the `WHERE` clauses for every request.

## Key Takeaway
Do **NOT** remove these filters from `wsgi_handler.py`. They are the final gatekeeper for data quality on the dashboard.
