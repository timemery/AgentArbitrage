# Fix Token Starvation & Upserter Frequency

**Date:** 2026-02-05
**Status:** SUCCESS
**Files Modified:**
- `celery_config.py`
- `keepa_deals/token_manager.py`

## Overview
The system was experiencing a persistent "Deal Starvation" issue where the dashboard deal count remained stuck (e.g., at 62 deals) despite healthy diagnostics. The root cause was identified as a resource contention issue between the `Upserter` (Live Updates) and `Backfiller` (Historical Data) tasks, exacerbated by an extremely low Keepa API refill rate (5 tokens/minute).

## Challenges & Diagnosis
*   **The "Green Dashboard" Trap:** All system health checks passed. Redis was connected, Celery was running, and locks were active. This masked the fact that the system was technically "working" but physically unable to process data.
*   **The Math of Starvation:**
    *   **Refill Rate:** 5 tokens/minute.
    *   **Upserter Cost:** ~5-10 tokens per run (to check page 0).
    *   **Upserter Frequency:** Scheduled every 1 minute (`crontab(minute='*')`).
    *   **Result:** The Upserter was consuming 100% of the available refill capacity. The `Backfiller`, which requires a buffer of ~80-180 tokens to start a batch, never saw the token bucket fill up enough to execute. It was perpetually waiting for a surplus that never arrived.
*   **Priority Inversion:** Although we previously adjusted thresholds to give the Upserter priority, we didn't account for the fact that the Upserter *itself* was running so often that it prevented the accumulation of tokens needed for the lower-priority task.

## Solutions Implemented

### 1. Reduced Upserter Frequency
Modified `celery_config.py` to change the `update_recent_deals` schedule from **every minute** to **every 10 minutes**.
*   **Old:** `minute='*'` (60 runs/hour * 5 tokens = 300 tokens/hour).
*   **New:** `minute='*/10'` (6 runs/hour * 5 tokens = 30 tokens/hour).
*   **Impact:** With a refill rate of 300 tokens/hour (5/min), this frees up ~270 tokens/hour for the Backfiller. This allows the token bucket to "breathe" and accumulate the surplus needed for heavier backfill operations between Upserter runs.

### 2. Low Refill Rate Warning
Added a critical warning in `keepa_deals/token_manager.py`.
*   If the API reports a `refillRate` less than 10 tokens/minute, the system now logs:
    `CRITICAL: Keepa Refill Rate is extremely low (5.0/min). Deal collection will be severely throttled. Upgrade Keepa plan to improve speed.`
*   This ensures that future debugging immediately identifies the physical constraint rather than chasing code bugs.

## Technical Notes for Future Agents
*   **API Limits are Physical Laws:** You cannot code your way out of a 5 token/minute limit. If a task runs every minute and costs 5 tokens, *nothing else can run*.
*   **Scheduling is Rate Limiting:** In low-throughput environments, the Celery schedule (`celery_config.py`) is just as important as the code-level rate limiter (`TokenManager`).
*   **Diagnostics:** If `Backfiller` is "Waiting for tokens" for hours, check the `Upserter` frequency and the global `refillRate`.
