# Dev Log: Janitor Aggression & Dashboard Notification Disparity Investigation

**Date:** December 24, 2025 **Task:** Investigate why the "Janitor" task was deleting deals faster than the backfiller could update them, and resolve a disparity between the "New Deals Found" notification count and the actual number of deals displayed on the dashboard.

## 1. Issue Overview

The user reported two related issues:

1. **Low Deal Retention:** Despite the backfiller successfully processing hundreds of deals, the dashboard often showed very few (<100). The user suspected the "Janitor" task (responsible for cleaning stale data) was too aggressive.
2. **Misleading Notifications:** The "Refresh Deals" button would notify the user of "185 new deals found," but clicking it would only load ~88 deals into the grid. This created a poor user experience and confusion about data integrity.

## 2. Technical Investigation & Root Cause Analysis

### A. The Janitor's "Grace Period"

- **Finding:** The `clean_stale_deals` task deletes records where `last_seen_utc` is older than a specific threshold (`grace_period_hours`).
- **Configuration Mismatch:** While the code had a default of 72 hours, the active configuration in `celery_config.py` explicitly passed `kwargs={'grace_period_hours': 24}`.
- **The "Manual Trigger" Bug:** Crucially, the manual API endpoint (`/api/run-janitor` in `wsgi_handler.py`), which is triggered when the user clicks "Refresh Deals", had a **hardcoded** value of `grace_period_hours=24`.
- **Impact:** Even if the background task was configured correctly, every time the user manually refreshed the dashboard to see new data, they inadvertently wiped out any deal between 24 and 72 hours old. This created a race condition where the backfiller (which might take days to cycle through all deals) couldn't update records fast enough to save them from the user's manual refresh.

### B. Notification Disparity

- **Finding:** The dashboard polling logic (`dashboard.html`) compared the local table count against the total record count returned by `/api/deal-count`.
- **The Flaw:** The `/api/deal-count` endpoint returned the *unfiltered* total count of the `deals` table. The dashboard grid, however, applies default filters (e.g., Min Margin > 0%).
- **Impact:** If the database contained 185 deals, but 97 of them had negative margins, the notification would say "185 deals found," but the grid would only render the 88 positive-margin deals. This was technically correct (the deals *did* exist) but misleading to the user.

## 3. Solutions Implemented

### A. Fix: Extending Data Retention

1. **Configuration Update:** Modified `celery_config.py` to increase `grace_period_hours` from 24 to **72**. This allows deals to persist for 3 days without an update, giving the backfiller ample time to cycle back to them.
2. **Code Fix:** Updated `wsgi_handler.py` to use `grace_period_hours=72` in the `run_janitor` function, ensuring manual refreshes no longer aggressively delete valid data.
3. **Documentation:** Updated `Feature_Deals_Dashboard.md` to reflect the new 72-hour policy.

### B. Fix: Filter-Aware Notifications

1. **Backend (`wsgi_handler.py`):** Updated the `/api/deal-count` endpoint to accept the same query parameters as the main data endpoint (`sales_rank_current_lte`, `margin_gte`, `keyword`). It now constructs a dynamic `WHERE` clause to return a count that matches the active filters.
2. **Frontend (`dashboard.html`):** Updated the JavaScript polling function to retrieve the current values from the filter inputs and append them to the polling URL. The notification logic now compares the *filtered* server count against the *filtered* local count.

### C. Diagnostic Tooling

- Created `Diagnostics/verify_api_counts.py`. This script connects directly to the SQLite database to get a raw row count and compares it against the API's reported count. This provides a definitive way to verify if "missing" deals are due to database deletion or API filtering.

## 4. Results & Verification

- **Janitor:** The user confirmed that deals are no longer disappearing aggressively.
- **Notifications:** The user verified that after the fix, the discrepancy disappeared. The "Refresh" link now accurately reflects the data visible in the grid (e.g., showing no "New Deals" when the new items are hidden by filters).
- **Stats Alignment:** The `count_stats.sh` (log-based) and `verify_api_counts.py` (DB-based) scripts were used to confirm that data ingestion is proceeding correctly and that the database state matches the logs.

**Status:** Successful. The system is stable, data retention is improved, and UI feedback is accurate.
