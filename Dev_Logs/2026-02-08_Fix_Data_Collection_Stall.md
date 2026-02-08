# Fix Data Collection Stall: Incremental Backfill & Dynamic Throttling

**Date:** 2026-02-08
**Status:** SUCCESS
**Files Modified:** `keepa_deals/backfiller.py`, `keepa_deals/simple_task.py`

## Problem Overview
The system had not collected any new deals for over 44 hours, despite the "System Health" diagnostics reporting that all services (Celery, Redis, Database) were running correctly. The deal count was stuck at 264, and the Backfill Page was stuck at 4.

## Diagnosis
The root cause was identified as a "Livelock" caused by the interaction between the system's batch processing logic and the extremely low Keepa API refill rate (5 tokens/minute) on the current plan.

1.  **Backfiller Stall (Infinite Loop):**
    *   The `backfill_deals` task was designed to save its progress (`backfill_page`) only after successfully processing an *entire page* (approx. 100 deals).
    *   On a 5 token/min plan, fetching and processing 100 deals (even with the optimized "Peek Strategy") requires significantly more time/tokens than can be accumulated in a single run without timing out or hitting external limits.
    *   Consequently, the task would inevitably fail or restart *before* completing Page 4.
    *   Upon restart, it would reload "Page 4" from the database and start from the beginning of the page again, reprocessing the same deals, burning tokens, and never making forward progress.

2.  **Upserter Starvation:**
    *   The `update_recent_deals` (Upserter) task was configured to fetch up to 200 new deals (`MAX_NEW_DEALS_PER_RUN`).
    *   Fetching 200 deals (Heavy Fetch) costs ~4000 tokens. With a refill rate of 5/min, this is impossible to achieve in a reasonable timeframe.
    *   The task would time out waiting for tokens, often without updating the watermark, leading to repeated attempts to fetch the same "new" deals.

## Solution Implemented

### 1. Incremental Backfill State (`keepa_deals/backfiller.py`)
*   **Chunk-Level Tracking:** Implemented a new state variable `backfill_chunk_index` in the `system_state` table.
*   **Granular Saves:** Modified the main processing loop to save state (Page + Chunk Index) after *every* successful chunk (4 deals), rather than waiting for the whole page.
*   **Resume Logic:** Updated `load_backfill_state` and the loop initialization to skip already-processed chunks when restarting a page.
*   **Result:** The Backfiller can now make incremental progress (e.g., process 4 deals, run out of tokens, pause/restart, resume at deal 5).

### 2. Dynamic Upserter Throttling (`keepa_deals/simple_task.py`)
*   **Adaptive Limits:** Implemented logic to check `token_manager.REFILL_RATE_PER_MINUTE` at startup.
*   **Load Shedding:** If the refill rate is `< 20 tokens/min`, the `MAX_NEW_DEALS_PER_RUN` is automatically reduced from **200** to **20**.
*   **Result:** The Upserter can now complete a full "run" (fetch -> process -> upsert -> update watermark) within the constraints of the token bucket, ensuring the "Newest Deal Age" stays fresh even on low-tier plans.

## Verification
*   **Logs:** Confirmed that the Backfiller is now logging `Resuming backfill from page 4, chunk X`, proving the incremental state is working.
*   **Progress:** The "Total Processed" count in diagnostics began increasing (853 -> 862) immediately after the fix.
*   **Token Consumption:** Verified that "phantom" token drops were actually legitimate bursts of activity from the Backfiller processing chunks, followed by correct entry into "Recharge Mode" (waiting for 80 tokens) to prevent starvation.

## Outcome
The data collection pipeline is now robust against low-bandwidth conditions. It operates in a "Burst and Wait" cycle, making slow but steady progress without stalling or looping.
