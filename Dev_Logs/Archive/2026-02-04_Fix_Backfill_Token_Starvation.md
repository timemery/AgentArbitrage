# Fix Backfill Token Starvation & Deadlock

**Date:** 2026-02-04
**Status:** SUCCESS
**Files Modified:** `keepa_deals/backfiller.py`, `keepa_deals/token_manager.py`

## Overview
The system was experiencing a severe stall in the "Deals Collection" (Backfill) process. The Backfill Lock was held for extended periods (240+ hours in some diagnostics), but no new deals were being ingested, and the token balance was hovering just below the configured threshold.

Diagnostics revealed two critical issues causing a "Deadlock" and a "Livelock":
1.  **The Deadlock (Target 480):** The Backfiller was attempting to reserve tokens for an entire chunk of 20 new ASINs at once. With a cost of 20 tokens per ASIN, the total request was 400 tokens. The TokenManager requires `Cost + Buffer (80) = 480` tokens to proceed. However, the Keepa API bucket size is typically 300. It is physically impossible to reach 480 tokens, causing the task to wait infinitely.
2.  **The Livelock (Starvation):** The Backfiller had a high `MIN_TOKEN_THRESHOLD` (150) to "protect" the Upserter. However, the Upserter (Threshold 50) runs every minute and consumes the small trickle of refilled tokens (5/min), preventing the balance from ever accumulating back up to 150.

## Challenges & Diagnosis
*   **Invisible Deadlock:** The logs initially just showed "Waiting..." without explaining *why*. We added enhanced diagnostics to `TokenManager` to log `Current vs Target` tokens, which immediately revealed the `Target: 480` impossibility.
*   **Slow Refill:** The refill rate was observed at 5 tokens/min, exacerbating the starvation issue.

## Solution Implemented

### 1. Batching Strategy (`keepa_deals/backfiller.py`)
We modified the backfill logic to process new ASINs in smaller batches instead of all at once.
*   **Previous:** Request 20 ASINs -> Cost 400 -> Target 480 (Deadlock).
*   **New:** Request batches of 5 ASINs -> Cost 100 -> Target 180 (Safe).
*   **Implementation:** Added `BACKFILL_BATCH_SIZE = 5` and an inner loop to process the `new_asins` list.

### 2. Threshold Tuning
*   Reduced the `MIN_TOKEN_THRESHOLD` for the Backfiller from **150** to **80**.
*   **Rationale:** 80 is still higher than the Upserter's threshold (50), maintaining the priority/protection window, but it is low enough to be reachable even with a slow refill rate.

### 3. "Controlled Deficit" Strategy (`keepa_deals/token_manager.py`)
We updated `request_permission_for_call` to fully implement the "Controlled Deficit" pattern documented in the system architecture.
*   **Logic Change:** Instead of checking if `Resulting Balance > Threshold`, we now check if `Starting Balance > Threshold`.
*   **Impact:** This allows the system to "burn" tokens into the negative (using the Keepa deficit allowance) as long as we started from a healthy state. This significantly increases throughput by utilizing the full depth of the token bucket.

## Result
*   Diagnostics confirm the Backfiller is now successfully processing batches (`Fetching batch of 5 ASINs...`).
*   Token consumption is observed (`Tokens consumed: 22... 50`), proving the lock is no longer stalled.
*   The "Insufficient tokens" warnings now show reachable targets (e.g., Target 180), which clears rapidly.

## Verification
*   Ran `verify_batching.py` (mock) to confirm the batch loop logic.
*   Ran `verify_deficit.py` to confirm the TokenManager logic allows deficits when appropriate.
*   User confirmed success via production logs.
