# 2026-01-26 - Fix Deal Ingestion Stall (Rate Limiting & Retries)

## Task Overview

The user reported "insanely slow data collection" and "obsolete data" (deals stuck days in the past). Diagnostic tools confirmed the ingestion pipeline was stalled:
-   **No new deals** were being ingested.
-   **Watermark was stuck** or drifting into the future.
-   **Logs showed 429 Errors** (Too Many Requests) from Keepa API, which were causing the tasks to abort silently or fail to pagination.

## Root Cause Analysis

1.  **Swallowed 429 Errors:**
    The `fetch_deals_for_deals` function in `keepa_api.py` was catching *all* `requests.exceptions.RequestException` errors and returning `None`.
    -   **Impact:** When the Keepa API returned a 429, the function silently returned `None`. The `simple_task` (Upserter) interpreted `None` as "No more deals found" and stopped pagination immediately.
    -   **Result:** The task would start, hit a rate limit on Page 0, think "Job Done", and exit. It never waited, never retried, and never got new data.

2.  **Lack of Retry Logic in Upserter:**
    The `simple_task.py` (Upserter) had a single-pass loop. If the first attempt to fetch Page 0 failed (e.g., due to a 429 or network blip), the entire task cycle was wasted.

## Actions Taken

1.  **Refactored `keepa_deals/keepa_api.py`:**
    -   Modified `fetch_deals_for_deals` to check the status code of exceptions.
    -   **Change:** Now **re-raises** exceptions if the status code is **429** (Too Many Requests) or **5xx** (Server Error). This allows the `@retry` decorator (already present) to actually work.
    -   **Optimization:** Before raising, it opportunistically extracts the `tokensLeft` from the 429 error body and updates the `TokenManager`. This ensures the system knows the bucket is empty and waits appropriately before the next attempt.

2.  **Enhanced `keepa_deals/simple_task.py`:**
    -   Wrapped the critical "Page 0" fetch in a **Retry Loop** (3 attempts with backoff).
    -   **Change:** If `fetch_deals_for_deals` fails or returns `None` on the first page, the task now waits (15s, 30s, 45s) and retries rather than giving up.
    -   **Logging:** Added specific logging for the "Stop Trigger" (when a deal is older than the watermark) to distinguish between "API Failure" and "Actual Data Catch-up".

3.  **Watermark & Backfill Reset:**
    -   Created/Updated `Diagnostics/manual_watermark_reset.py` to forcibly reset the system watermark to "24 Hours Ago" (Server Time).
    -   This broke the "Future Watermark" paralysis where the system refused to import "old" data.
    -   Triggered a full system reset (`--reset`) to wipe the "obsolete" database and start fresh.

## Verification

-   **Diagnostic:** `Diagnostics/repro_fetch_status.py` verified the new behavior (timeout/wait on low tokens instead of silent failure).
-   **Unit Tests:** `tests/test_simple_task_logic.py` passed.
-   **Deployment:** User successfully deployed, wiped the logs/DB, and triggered a fresh backfill.

## Conclusion

The system is now robust against Keepa API rate limits. Instead of aborting silently when the bucket is empty, it will:
1.  Capture the 429.
2.  Update the internal Token Manager (0 tokens).
3.  Wait for the required refill time.
4.  Retry the request.

This ensures a steady stream of data ingestion even under heavy load.
