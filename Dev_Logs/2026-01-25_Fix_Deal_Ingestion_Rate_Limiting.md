# Fix Deal Ingestion Rate Limiting & "Missing List at" Investigation

## Problem
The user reported a "Loss of Deals" and "Continuing Loss of Deals" from the database, with a suspicion that the "Missing List at" rejection (100% of rejections) was the cause.
Diagnostic logs revealed:
1.  **Ingestion Stall:** No new deals had been ingested for ~54 hours.
2.  **API Errors:** `429 Client Error: Too Many Requests` were occurring when fetching new deals (`fetch_deals_for_deals`).
3.  **Token Depletion:** The system was running with negative tokens (-21) and failing immediately upon trying to fetch deals.

## Root Cause Analysis
1.  **429 Errors (Primary Cause):** The function `fetch_deals_for_deals` in `keepa_deals/keepa_api.py` did not use the `TokenManager`. It executed API calls immediately. If the token bucket was empty (e.g., consumed by other tasks like `backfiller` or `update_recent_deals`), the call failed with a 429 error. This blocked the `simple_task` from fetching *any* new deals.
2.  **Missing 'List at' (Secondary Observation):** The 100% rejection rate for "Missing List at" reported by the user was misinterpreted. It meant "100% of the *rejected* deals were due to this reason," not "100% of *all* deals". The actual rejection rate was ~30%, which is normal. The "Missing List at" is triggered when the AI Reasonableness Check fails. Investigation showed the AI is correctly identifying risky items (e.g., "Used Digital Pack").

## Solution
1.  **Rate Limiting Fix:**
    *   Modified `fetch_deals_for_deals` in `keepa_deals/keepa_api.py` to accept an optional `token_manager`.
    *   If a `token_manager` is provided, the function now calls `token_manager.request_permission_for_call(estimated_cost=10)` before the API call. This forces the process to sleep and wait for tokens instead of crashing with a 429.
2.  **Task Updates:**
    *   Updated `keepa_deals/simple_task.py` (Upserter) to pass its `token_manager` to `fetch_deals_for_deals`.
    *   Updated `keepa_deals/backfiller.py` to pass its `token_manager` to `fetch_deals_for_deals`.

## Verification
*   **Diagnostic Script:** `Diagnostics/debug_deal_rejection.py` (newly created) ran successfully without 429 errors, confirming the token wait logic works.
*   **Deal Analysis:** The diagnostic script processed 3 deals:
    *   1 Rejected (Valid AI rejection for Used Digital Pack).
    *   2 Accepted.
    *   This confirms the system logic is sound and not rejecting everything.
*   **Tests:** `tests/test_simple_task_logic.py` and `tests/test_stable_calculations.py` passed.

## Outcome
The deal ingestion pipeline should now recover. The `simple_task` will wait for tokens instead of aborting, ensuring steady (if throttled) ingestion of new deals to replace the expiring ones.
