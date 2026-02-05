# Dev Log: Fix Deal Stagnation and Token Starvation Livelock

**Date:** 2026-02-05
**Author:** Jules
**Task:** Fix Deal Stagnation / Token Starvation

## Overview
The system was experiencing "Deal Stagnation" where the `Backfiller` task was permanently stalled (holding a lock but not processing) and the `Upserter` task was running but struggling to find new deals.

Diagnostics revealed the root cause was a **"Token Starvation Livelock"** exacerbated by an extremely low Keepa API refill rate (5 tokens/minute).

## Challenges Faced
1.  **Extreme Resource Scarcity:** The Keepa API refill rate was confirmed to be 5 tokens/minute (300/hour). Previous configurations assumed a much higher rate (10-20/min).
2.  **Livelock Condition:**
    *   The `Backfiller` was configured to wait for a "safe" buffer of **80 tokens** (`MIN_TOKEN_THRESHOLD`).
    *   The `Upserter` (`simple_task.py`) ran every **10 minutes** and consumed **~60-100 tokens** per run.
    *   This dynamic kept the token bucket permanently oscillating in the `[0, 60]` range. It never reached the **80** required for the Backfiller to resume, yet the Backfiller held the lock indefinitely while waiting.
3.  **Sandbox Environment Limitations:**
    *   The sandbox lacked a running Redis server and `sudo` privileges.
    *   Scripts like `./deploy_update.sh` and `Diagnostics/run_suite.sh` failed their infrastructure checks, preventing end-to-end runtime verification.
    *   We had to rely on code analysis, unit test simulations (`tests/test_token_contention.py`), and manual code application.

## Actions Taken
To resolve the livelock and align the system with the 5 token/min constraint:

1.  **Aligned Backfiller Threshold:**
    *   Modified `keepa_deals/backfiller.py` to reduce `MIN_TOKEN_THRESHOLD` from **80** to **50**.
    *   *Effect:* This puts the Backfiller on equal footing with the Upserter (which also uses 50), allowing it to compete for tokens rather than being permanently starved.

2.  **Reduced Upserter Burst Cost:**
    *   Modified `keepa_deals/simple_task.py` to reduce `MAX_ASINS_PER_BATCH` from **5** to **2**.
    *   *Effect:* This lowers the cost of a "heavy" upsert batch from ~100 tokens to ~40 tokens. This prevents the Upserter from draining the bucket completely in a single burst, leaving crumbs for the Backfiller.

3.  **Optimized Schedule:**
    *   Modified `celery_config.py` to change the `update-recent-deals-every-minute` schedule from `*/10` to **`*/15`** minutes.
    *   *Effect:* A 15-minute interval at 5 tokens/min generates **75 tokens**. Since the task consumes ~60 tokens, this schedule is sustainable and allows a small surplus to accumulate over time, eventually enabling the Backfiller to run.

4.  **Deployment:**
    *   Executed `./deploy_update.sh`. While the service restart phase failed (expected in sandbox), the code files on disk were successfully updated.

## Outcome
**Successful (Logic & Code).**
The changes mathematically resolve the starvation issue by reducing demand to match supply.

*   **Before:** Demand > Supply (Net Negative), High Threshold (80) unreachable.
*   **After:** Demand <= Supply (Net Neutral/Positive), Lower Threshold (50) reachable.

**Next Steps:**
*   Monitor `celery_worker.log` in production to confirm the `Backfiller` successfully acquires tokens and advances the page count.
*   Verify that `last_seen_utc` timestamps in the dashboard are updating roughly every 15-30 minutes.
