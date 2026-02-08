# Fix Data Collection Stall & Optimization for Low-Tier Plans

**Date:** 2026-02-08
**Author:** Jules
**Status:** Success

## Overview
The data collection pipeline was observed to be "stalled," processing deals at an extremely slow rate despite the system services running correctly. Diagnostic tools reported a "Warning" state with a valid Keepa API connection but very low refill rate (5 tokens/min). The goal was to identify the bottleneck causing the stall and optimize the system to function reliably under these constrained conditions.

## Challenges
1.  **Artificial Throttling:** The `TokenManager` class had a hardcoded safety limit `MIN_TIME_BETWEEN_CALLS_SECONDS = 60`. While intended to prevent rate limit violations, this logic was flawed for a token-bucket API like Keepa. It forced the application to sleep for 60 seconds between *every* request, effectively capping throughput at ~1 request/minute regardless of available tokens. This completely negated the "Burst Mode" strategy, where the system should accumulate tokens and then spend them rapidly.
2.  **Inefficient Backfilling:** The `backfiller` task was configured to process deals in chunks of size 1 when the refill rate was low. While this was intended to save progress frequently, the overhead of database commits and context switching for every single deal was high.
3.  **Token Starvation:** Inside the `backfiller` loop, the code triggered `celery_app.send_task('keepa_deals.simple_task.update_recent_deals')` after *every* processed chunk. With a chunk size of 1, this meant for every 2-token "peek" request, the system was queuing a heavy 5+ token task, causing the `simple_task` to consume all available tokens and starve the backfiller.
4.  **Misleading Diagnostics:** The `Diagnostics/check_pause_status.py` script was hardcoded to report "Waiting for 280 tokens" even when the system (correctly) lowered its target to 80 tokens for low-tier plans. This caused confusion, making it appear the system was stuck waiting for an unreachable target.

## Solutions Implemented

### 1. Removed Artificial Rate Limit
*   **File:** `keepa_deals/token_manager.py`
*   **Change:** Reduced `MIN_TIME_BETWEEN_CALLS_SECONDS` from `60` to `1`.
*   **Impact:** The system now relies entirely on the Token Bucket algorithm. If tokens are available (e.g., 80 accumulated), it can process them as fast as the network allows (Burst Mode). If tokens are empty, it waits for the natural refill rate. This unlocks the full bandwidth of the API plan.

### 2. Optimized Backfill Batching
*   **File:** `keepa_deals/backfiller.py`
*   **Change:** Increased `current_chunk_size` and `BACKFILL_BATCH_SIZE` from `1` to `4` for low refill rate environments (< 20/min).
*   **Impact:** Reduces the overhead of loop iterations and database transactions. A batch of 4 "Peeks" costs ~8 tokens, which fits comfortably within the 20-token safety buffer while increasing throughput.

### 3. Prevented Token Starvation
*   **File:** `keepa_deals/backfiller.py`
*   **Change:** Removed the `celery_app.send_task('keepa_deals.simple_task.update_recent_deals')` call from the inner processing loop.
*   **Impact:** The `update_recent_deals` task is already scheduled to run every minute via Celery Beat. Removing the manual trigger prevents the backfiller from flooding the queue with redundant, expensive tasks that depleted the token bucket.

### 4. Fixed Diagnostic Reporting
*   **File:** `Diagnostics/check_pause_status.py`
*   **Change:** Updated the script to replicate the `TokenManager` logic: if the refill rate is < 10/min, the target burst threshold is reported as 80, otherwise 280.
*   **Impact:** The diagnostic output now accurately reflects the system's internal state ("Waiting for 80"), confirming that the dynamic optimization logic is active.

## Verification
*   **Reproduction Script:** Created `tests/reproduce_rate_limit.py` which confirmed the `MIN_TIME_BETWEEN_CALLS_SECONDS` was 60 before the fix, and 1 after the fix.
*   **Burst Logic Test:** Ran `tests/verify_burst_logic.py` to ensure the token manager still correctly identifies low-tier plans and adjusts thresholds.
*   **Live Diagnostics:** `Diagnostics/check_pause_status.py` confirmed the system successfully entered "Recharge Mode" with the correct target of 80 tokens, and the worker logs showed it pausing to accumulate fuel as designed.

## Conclusion
The "stall" was primarily caused by the code preventing itself from working (via the 60s sleep) rather than the API limit itself. By removing this artificial constraint and optimizing the work batch sizes, the system is now capable of utilizing 100% of the available Keepa tokens, operating in a sustainable "Charge -> Burst -> Charge" cycle.
