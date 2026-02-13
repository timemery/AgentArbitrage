# Dev Log: Optimize Data Collection Speed (Decoupled Batching)

**Date:** 2026-02-13
**Task:** Improve Data Collection Speed (Decoupled Batching)
**Status:** SUCCESS

## 1. Overview
The objective of this task was to significantly increase the scanning throughput of the `Smart Ingestor` without compromising data accuracy or risking token starvation. The legacy system used a fixed batch size of 5 for all stages, which was safe but slow due to HTTP latency. The goal was to increase the "Peek" (Discovery) batch size to 50 while keeping the expensive "Commit" (Ingestion) batch size low.

## 2. Implementation Strategy: Decoupled Batching
We refactored `keepa_deals/smart_ingestor.py` to decouple the processing stages:

*   **Stage 1: Scan/Peek (Batch Size 50):** Fetches lightweight stats for 50 ASINs at once. This reduces HTTP overhead by 10x for the discovery phase.
*   **Stage 2: Commit (Batch Size 5):** Survivors of the Peek filter are processed in smaller sub-batches of 5. This prevents "Deficit Shock" (consuming 1000+ tokens instantly) if a high percentage of items pass the filter.
*   **Stage 3: Light Update (Batch Size 50):** Existing deals are updated in large batches for efficiency.

## 3. Challenges & Solutions

### Challenge A: Keepa API Limitations (`offers=0`)
*   **Hypothesis:** We could reduce Peek costs to ~1 token/ASIN by requesting `offers=0`.
*   **Reality:** The Keepa Product API returns `HTTP 400 Bad Request` for `offers=0`. Using `offers=1` often returned incomplete data (missing stats).
*   **Resolution:** We retained `offers=20` for the Peek stage.
    *   *Verification:* Diagnostic tests showed the cost for 50 ASINs with `offers=20` is ~250 tokens (~5 tokens/ASIN).
    *   *Safety:* Since the Keepa bucket size is 300 (with a burst threshold of 280), a single batch of 250 is safe *provided the bucket is full*.

### Challenge B: "Deficit Shock" & Worker Blocking
*   **Issue:** The high-speed ingestion quickly drained tokens, pushing the balance deep into negative territory (e.g., `-160 tokens`). The `TokenManager` calculated a recharge time of ~40 minutes.
*   **Critical Failure:** The `TokenManager` implemented this wait by **sleeping** (`time.sleep()`). This blocked the Celery worker thread while holding the `smart_ingestor_lock`. As a result, no other tasks could run, and the scheduler piled up "Task already running" logs.
*   **Resolution:**
    *   Implemented `TokenRechargeError` in `keepa_deals/token_manager.py`.
    *   If the required wait time exceeds **60 seconds**, the manager now raises this exception instead of sleeping.
    *   The `SmartIngestor` catches this exception, **releases the Redis lock**, and exits gracefully. This frees the worker to handle other tasks while the tokens passively recharge.

### Challenge C: API Drain during Recharge
*   **Issue:** During a long recharge (e.g., 40 mins), the system would wake up every minute (triggered by Cron), call `sync_tokens()` to check the balance, and exit. These status checks consume bandwidth and potentially small token amounts, slowing recovery.
*   **Resolution:**
    *   Implemented `get_projected_tokens()` and `should_skip_sync()` in `TokenManager`.
    *   The system now locally estimates the token balance based on the last known timestamp and refill rate.
    *   If the local estimate indicates we are still deep in the hole, the API `sync_tokens()` call is skipped entirely.

## 4. Verification
*   **Unit Tests:** Created `tests/test_smart_ingestor_batching.py` which validates:
    1.  Correct batch splitting (50 for Peek, 5 for Commit).
    2.  Graceful exit and lock release upon `TokenRechargeError`.
    3.  Skipping logic for `sync_tokens`.
*   **Live Diagnostics:** Confirmed that the system enters "Recharge Mode," releases the lock (allowing diagnostics to run), and successfully recovers from deficits.

## 5. Conclusion
The system now possesses a "Burst Mode" capability. It will ingest data at max speed until tokens are depleted, cleanly exit to recharge, and automatically resume once the bucket is full. This maximizes utility of the Keepa API quota.
