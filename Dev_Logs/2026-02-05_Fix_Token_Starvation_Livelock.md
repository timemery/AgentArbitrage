# Fix Token Starvation Livelock (Backfiller Stalled)

**Date:** 2026-02-05
**Status:** SUCCESS
**Files Modified:**
- `keepa_deals/token_manager.py`
- `keepa_deals/backfiller.py`
- `tests/test_token_threshold.py` (New)

## Overview
The system was experiencing a "Livelock" scenario where the `Backfiller` task was permanently stalled, despite having a moderate amount of tokens (e.g., 37). The root cause was a mismatch between the configured `MIN_TOKEN_THRESHOLD` (50) and the extremely low physical refill rate of the Keepa API (5 tokens/minute).

## Challenges & Diagnosis
*   **The 50-Token Wall:** The `Backfiller` was hardcoded to wait until 50 tokens were available (`MIN_TOKEN_THRESHOLD = 50`).
*   **The Sisyphus Cycle:**
    *   Refill Rate: 5 tokens/min.
    *   Time to reach 50 tokens from 0: ~10 minutes.
    *   Competing Task: The `Upserter` (Simple Task) runs every 15 minutes and consumes ~20-40 tokens.
    *   **Result:** The token bucket would slowly climb to ~30-40, then the Upserter would run and knock it back down. The Backfiller, waiting specifically for **50**, would never see its condition met. It would wait indefinitely, holding the `backfill_deals_lock`.
*   **Log Evidence:** Diagnostic logs showed the worker repeatedly looping:
    `Insufficient tokens (Current: 37.00, Target: 50). Waiting for 216s.`

## Solutions Implemented

### 1. Reduced Minimum Token Threshold
Modified `keepa_deals/token_manager.py` and `keepa_deals/backfiller.py` to reduce `MIN_TOKEN_THRESHOLD` from **50** to **20**.
*   **Rationale:** With a refill rate of 5/min, a buffer of 20 tokens (4 minutes of refill) is sufficient to prevent immediate API errors for small batches, while being reachable enough to allow tasks to start.
*   **Impact:** This lowers the "activation energy" required for the Backfiller, allowing it to seize the lock and process deals even when the tank is not full.

### 2. Verification Testing
Created `tests/test_token_threshold.py` to mathematically verify the `TokenManager` logic:
*   Confirmed that requests are **Allowed** when `tokens >= 20`.
*   Confirmed that requests are **Denied** when `tokens < 20` (unless priority/controlled deficit rules apply).
*   Mocked external API calls to prevent "400 Client Error" noise in test logs.

## Outcome
**Verified Fix.**
Subsequent diagnostics confirmed that the `Backfiller` successfully started processing a batch with **20 tokens** available (`Target: 20`), which would have previously stalled. The system is now efficiently utilizing the limited 5 token/min bandwidth without artificial deadlocks.

## Technical Notes
*   **Low-Resource Tuning:** In environments with strict API limits (e.g., Keepa < 10/min), standard "safety buffers" (like 50 or 100 tokens) effectively become "denial of service" thresholds. Thresholds must be scaled down proportional to the refill rate.
*   **Test Noise:** When testing components that make network calls (`keepa_api`), always mock the network layer (`unittest.mock.patch`) to avoid misleading error logs and environmental dependencies.
