# Fix Token Drift and Stalled Data Collection

**Date:** 2026-01-29
**Task:** Investigate and fix inaccurate token availability reporting and stalled data collection.
**Status:** SUCCESS

## Overview
The user reported two related issues:
1.  **Inaccurate Token Counts:** The application logs showed negative token balances (e.g., `-42.00`) and long wait times (e.g., `Waiting for 624 seconds`), while the Keepa dashboard showed a positive balance (e.g., `38` tokens). This discrepancy caused the system to sleep unnecessarily, stalling data collection.
2.  **Stalled Data:** Despite consuming tokens, no new deals were being saved to the database. The "Rejection Breakdown" showed high rejection rates, but the primary concern was that the system might be fetching old data.

## Challenges
*   **Process-Local State:** The `TokenManager` class maintains a local estimate of the token bucket. In a multi-worker Celery environment (prefork), each worker process has its own isolated instance of `TokenManager`. These instances do not communicate, causing their local estimates to drift significantly from the actual global state maintained by the Keepa servers. A worker effectively "blinded" by its own pessimistic estimate would sleep even when tokens were available.
*   **Diagnosis of "Stalled" Data:** It was unclear whether the lack of new deals was due to empty API responses, incorrect API parameters (e.g., wrong `sortType`), or valid filtering logic. The logs lacked sufficient detail to confirm if the API was truly returning "new" data.
*   **Environment Constraints:** The diagnostic script initially failed because the sandbox environment lacked the `python-dotenv` package and the `KEEPA_API_KEY` was not loaded, preventing live API verification during the debug phase.

## Solutions Implemented

### 1. Token Manager: Sync-Before-Wait Strategy
*   **File:** `keepa_deals/token_manager.py`
*   **Logic Change:** Modified the `request_permission_for_call` method. Before the system commits to a "Wait/Sleep" cycle (triggered by `tokens < MIN_TOKEN_THRESHOLD`), it now forces a call to `sync_tokens()`.
*   **Effect:** This fetches the *authoritative* token count from the Keepa API. If the local estimate was -42 but the API says 38, the system updates to 38 immediately. This prevents false positives where the worker sleeps for minutes due to incorrect local math. The system now only sleeps if the *server* confirms tokens are low.

### 2. Data Collection: Sort Order Sanity Check
*   **File:** `keepa_deals/simple_task.py`
*   **Enhancement:** Added a sanity check after fetching Page 0 of deals.
*   **Logic:** The system calculates the age of the newest deal. If the "newest" deal is older than 24 hours, it logs a `WARNING` suggesting that the `sortType: 4` (Last Update) parameter might be failing or ignored by the API.
*   **Logging:** Updated logs to explicitly state `Fetching deals using Sort Type: 4 (Last Update)` to ensure clarity in future debugging.

### 3. Diagnostic Tooling
*   **File:** `Diagnostics/verify_sort_behavior.py`
*   **Purpose:** A standalone script was created to manually verify the behavior of the Keepa API. It fetches deals using both `sortType=0` (Sales Rank) and `sortType=4` (Last Update) and compares the timestamps, providing definitive proof of whether the API is functioning as expected.

## Outcome
The user confirmed that the token count in the terminal now matches the Keepa dashboard. The unnecessary stalls have been eliminated, allowing the system to utilize available tokens efficiently. The added logging provides visibility into data freshness to monitor the "stalled data" issue moving forward.
