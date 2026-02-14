# Fix: Stalled Data Collection (Low Refill Rate Livelock)
**Date:** 2026-02-13
**Author:** Jules

## Overview
The Smart Ingestor was stalled at 86 deals for several days, despite the Celery task running every minute. Diagnostics revealed that while the system was technically "running", it was trapped in a "Livelock" state where it would wake up, check tokens, and immediately go back to sleep without processing any data. This occurred specifically on accounts with a low Keepa refill rate (5 tokens/min).

## Root Cause Analysis
1.  **Burst Threshold Mismatch:** The `TokenManager` enforces a `BURST_THRESHOLD` of **40 tokens** for low-rate accounts (< 10/min) to improve responsiveness (waiting for the standard 280 tokens would take ~56 minutes).
2.  **Batch Cost Exceeded Capacity:** The `Smart Ingestor` was defaulting to a `SCAN_BATCH_SIZE` of **20**. With `offers=20` enabled for accuracy, the cost per batch is ~100 tokens.
3.  **The Livelock Loop:**
    *   System waits for 40 tokens.
    *   System wakes up with 40 tokens.
    *   System attempts to reserve 100 tokens for a batch.
    *   `TokenManager` calculates `40 - 100 = -60`.
    *   While deficit spending is allowed, dropping below `MIN_TOKEN_THRESHOLD` (1) triggers "Recharge Mode" immediately for low-rate accounts to prevent starvation.
    *   The request is blocked, and the system goes back to sleep to recharge... but since it never spent the tokens, it wakes up again with 40, tries again, and fails again.

## The Solution
We implemented **Dynamic Batch Sizing** in `keepa_deals/smart_ingestor.py` to align the workload with the account's capacity.

*   **Logic:**
    ```python
    if token_manager.REFILL_RATE_PER_MINUTE < 10:
        current_batch_size = 5  # Cost ~25 tokens
    elif token_manager.REFILL_RATE_PER_MINUTE < 20:
        current_batch_size = 20 # Cost ~100 tokens
    else:
        current_batch_size = 50 # Cost ~250 tokens
    ```

*   **Result:**
    *   With a batch size of 5 (Cost ~25 tokens), the system can successfully reserve tokens from a 40-token burst bucket (`40 - 25 = 15`).
    *   The balance remains positive (15 > 1), avoiding the immediate "Recharge Mode" trigger.
    *   The batch processes successfully, the watermark advances, and the system naturally recharges the 25 tokens over the next ~5 minutes.

## Verification & Outcome
*   **Simulation:** A test script (`tests/verify_batch_sizes.py`) confirmed that throughput (deals/hour) is identical for Batch 5 and Batch 20 (limited by refill rate), but Batch 5 avoids blocking pauses.
*   **Production:** After deployment, the watermark advanced by **13.5 hours** in a single run, confirming the stall was broken.
*   **Status:** **SUCCESS**. The ingestion pipeline is unblocked.
    *   *Note:* The dashboard count remained at 86 initially because the first few batches of new deals were rejected by the filters (e.g., "Peek Rejected", "Profit <= 0"), but the *processing* is now active and healthy.

## Key Learnings
For API-limited systems, **Throughput != Batch Size**. Increasing batch size beyond the replenishment rate does not speed up ingestion; it only increases latency and the risk of resource starvation. Smaller, frequent batches are superior for stability on low-tier plans.
