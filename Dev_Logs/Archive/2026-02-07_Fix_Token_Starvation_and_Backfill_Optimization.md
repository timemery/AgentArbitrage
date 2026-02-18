# Fix Token Starvation, Livelock, and Backfill Throughput (2026-02-07)

## Problem Overview
The user reported that deal collection was "stuck" at 275 deals for over 20 hours despite multiple previous fixes. The system appeared to be running (workers active, locks held), but no new deals were appearing on the dashboard.

## Diagnosis
Investigation revealed a "Perfect Storm" of three compounding issues, exacerbated by the user's extremely low Keepa plan (5 tokens/minute):

1.  **Recharge Livelock:** The system was entering "Recharge Mode" (pausing to save up 280 tokens) but getting stuck there. If the token count drifted or a process crashed, there was no "timeout" to force a resume, leaving the system waiting forever for a target it might never reach.
2.  **Watermark Stagnation:** The `simple_task.py` (Upserter) had strict logic that refused to update the "Last Seen" watermark if the run was "incomplete" (interrupted by token limits). In a 5 token/min environment, *every* run is incomplete. This caused the task to re-fetch the exact same page of deals (Page 0) endlessly, never advancing to newer data.
3.  **Inefficient Rejection (The Bottleneck):** The `backfiller.py` treated "Zombie Deals" (deals with missing data in the DB) as "New/Repair Candidates". It forced them into the "Heavy Fetch" path (Cost: ~20 tokens) to try and fix them. Since most were genuinely bad (negative profit), the system was spending 20 tokens just to reject a deal.
    *   **Math:** 5 tokens/min refill ÷ 20 tokens/reject = **0.25 deals/minute** (1 deal every 4 minutes).
    *   To clear a backlog of 400 bad deals would take ~26 hours of continuous running.

## Solutions Implemented

### 1. TokenManager Safety Valve (Anti-Livelock)
*   **File:** `keepa_deals/token_manager.py`
*   **Change:** Implemented a **60-minute Timeout** for Recharge Mode.
*   **Logic:** If the system stays in "Recharge Mode" for more than 3600 seconds, it forces a resume regardless of the token count. This guarantees the system will never hang indefinitely, transforming a "permanent stall" into a "degraded but functional" hourly pulse.
*   **Diagnostics:** Updated `Diagnostics/check_pause_status.py` to show the recharge duration and start time.

### 2. Watermark Ratchet (Anti-Stagnation)
*   **File:** `keepa_deals/simple_task.py`
*   **Change:** Forced `should_update_watermark = True` even for incomplete runs.
*   **Logic:** If we fetch a batch of new deals and process them (even if we reject them), we *must* update the watermark to the timestamp of the deals we saw. This ensures the system "ratchets" forward through time, preventing infinite loops on bad data.

### 3. "Peek Strategy" Optimization (Throughput)
*   **File:** `keepa_deals/backfiller.py`
*   **Change:** Implemented "Two-Stage Fetching" for the New/Repair path.
*   **Stage 1 (Peek):** Fetch lightweight stats (Cost ~1-2 tokens). Check if the deal is even potentially viable (e.g., has a price).
*   **Stage 2 (Commit):** Only fetch the expensive Full History (Cost ~20 tokens) if the deal survives Stage 1.
*   **Impact:** Reduces the cost of rejecting a bad deal from 20 tokens to ~2 tokens.
*   **Result:** Increases scanning throughput by **~10x**, allowing the system to clear the backlog of invalid deals in hours instead of days.

## Verification
*   **Unit Test:** Created `tests/verify_recharge_timeout.py` to mathematically verify the TokenManager timeout logic (mocking time and Redis state).
*   **Live Logs:** Confirmed the "Heartbeat Cycle" is active:
    1.  **Burst:** Process deals efficiently (Peek Strategy).
    2.  **Pause:** Enter Recharge Mode when tokens < 20.
    3.  **Refill:** Wait ~45 minutes for 280 tokens.
    4.  **Resume:** Automatically burst again.

## Status
**SUCCESS.** The system is healthy, protected against livelocks, and optimized for the maximum possible throughput allowed by the user's API tier. The deal count will rise once the Backfiller clears the current "vein" of unprofitable data.
