# Fix Upserter Token Starvation

**Date:** 2026-02-04
**Status:** SUCCESS
**Files Modified:** `keepa_deals/simple_task.py`, `tests/verify_token_targets.py`

## Overview
The system was experiencing a critical "Deal Starvation" issue where no new deals were appearing on the dashboard for several days. Diagnostics revealed that while the `update_recent_deals` (Upserter) task was being scheduled correctly by Celery Beat, it was perpetually stuck in a "Waiting for tokens" state.

The root cause was identified as a **Priority Inversion** caused by the shared Token Bucket mechanism. The concurrently running `backfill_deals` (Backfiller) task had a lower "Activation Threshold" than the Upserter, allowing it to systematically drain the token pool before the Upserter could ever start.

## Challenges & Diagnosis
*   **Symptom:** Dashboard stuck at 62 deals.
*   **Log Analysis:**
    *   Upserter Log: `Insufficient tokens (Current: 24.00, Target: 250). Waiting...`
    *   Backfiller Log: Successfully running and consuming tokens.
    *   Refill Rate: ~5 tokens/minute.
*   **The Math of Starvation:**
    *   **Backfiller:** Batch Size 5 (Cost 100) + Threshold 80 = **Target 180**.
    *   **Upserter:** Batch Size 10 (Cost 200) + Threshold 50 = **Target 250**.
*   **The Mechanism:**
    *   As the token bucket slowly refilled from 0, it would inevitably hit **180** first.
    *   The Backfiller (waiting for 180) would immediately wake up, consume ~100 tokens, and drop the balance back to ~80.
    *   The Upserter (waiting for 250) would never see the balance reach its target, effectively being starved indefinitely.

## Solution Implemented

### 1. Priority Restoration via Batch Size Reduction
We reduced the `MAX_ASINS_PER_BATCH` in `keepa_deals/simple_task.py` from **10** to **5**.
*   **Old Upserter:** Cost 200 + Threshold 50 = Target 250.
*   **New Upserter:** Cost 100 + Threshold 50 = **Target 150**.

By lowering the Upserter's target to **150**, it is now *lower* than the Backfiller's target of **180**.
*   **New Flow:** As the bucket refills, it hits 150 first. The Upserter wakes up and runs. If the Backfiller is also waiting, it must wait until the balance reaches 180, which now only happens if the Upserter yields.
*   This effectively gives the **Live Updates** priority over **Historical Backfill**, which is the desired behavior.

### 2. Verification
A simulation script `tests/verify_token_targets.py` was created to model the refill rates and wait times.
*   **Pre-Fix:** Upserter Wait (2712s) > Backfiller Wait (1872s) -> **Starvation**.
*   **Post-Fix:** Upserter Wait (1512s) < Backfiller Wait (1872s) -> **Priority Restored**.

## Result
*   Production logs confirmed the Upserter immediately woke up, fetched 300 new deals, and updated the dashboard.
*   The system is now correctly balancing live updates with background backfilling.
