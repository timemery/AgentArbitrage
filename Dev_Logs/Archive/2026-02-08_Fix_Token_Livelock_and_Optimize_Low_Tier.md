# Fix Token Starvation Livelock & Optimize Low-Tier Plans (2026-02-08)

## Problem Overview
The user reported that deal collection was "stalled" at 264 deals for over 20 hours despite the system appearing to be running (workers active). Diagnostics revealed that the system was entering "Recharge Mode" (pausing to accumulate a large token buffer) but getting stuck in an infinite wait loop. This was exacerbated by the user's extremely low Keepa plan (5 tokens/minute), which made reaching the high recharge target (280 tokens) take nearly an hour, creating a perception of stagnation.

## Challenges
1.  **The "Livelock" Bug:** The `TokenManager` had a logic flaw where the `_wait_for_tokens` loop only checked for success (reaching the target). It did *not* check for the global timeout (60 minutes). If tokens were consumed faster than they refilled (or if the refill rate was extremely low), the loop would never exit, causing the worker to hang indefinitely.
2.  **Stalled Perception:** With a refill rate of 5 tokens/min and a `BURST_THRESHOLD` of 280, the system would pause for ~56 minutes every cycle. To the user, this looked like the system was broken ("stalled"), when it was actually just waiting efficiently.
3.  **Low Throughput:** The long wait times reduced the effective scanning window, limiting the number of deals processed per hour.

## Solutions Implemented

### 1. Fix Infinite Wait (Livelock Prevention)
*   **File:** `keepa_deals/token_manager.py`
*   **Change:** Added a check for the global `keepa_recharge_mode_active` timeout (60 minutes) *inside* the `_wait_for_tokens` loop.
*   **Result:** If the system is stuck waiting for > 60 minutes, it forces an exit, allowing the worker to clear the lock and resume processing. This ensures self-healing from any stuck state.

### 2. Optimize Burst Threshold (Responsiveness)
*   **File:** `keepa_deals/token_manager.py`
*   **Change:** Implemented dynamic adjustment of the `BURST_THRESHOLD`.
    *   **Logic:** If `REFILL_RATE_PER_MINUTE < 10` (e.g., 5.0), the target is lowered from **280** to **80**.
*   **Impact:**
    *   **Old Wait Time:** ~56 minutes (280 / 5).
    *   **New Wait Time:** ~16 minutes (80 / 5).
    *   **Benefit:** The system resumes much faster (40 minutes sooner), eliminating the perception of stalling and increasing the frequency of deal updates.

### 3. Manual Override Utility
*   **File:** `Diagnostics/force_resume_collection.py`
*   **Purpose:** A script to manually clear the Redis keys (`keepa_recharge_mode_active`, `keepa_recharge_start_time`) responsible for the pause. This allows operators to immediately unblock the system without waiting for the timeout.

## Verification
*   **Tests:**
    *   `tests/verify_wait_loop_timeout.py`: Confirmed that `_wait_for_tokens` correctly exits when the timeout is exceeded.
    *   `tests/verify_burst_logic.py`: Confirmed that the `BURST_THRESHOLD` switches correctly between 80 (low rate) and 280 (high rate).
*   **Diagnostics:**
    *   Logs confirmed: `[INFO] Low Refill Rate (5.0/min) detected. Adjusted Burst Threshold to 80`.
    *   Logs confirmed: `Burst threshold reached (198.00 >= 80). Exiting Recharge Mode.`
    *   Total Processed count increased from 774 to 830, proving the pipeline is active.

## Outcome
**SUCCESS.** The livelock is resolved, and the system is now optimized for the maximum physical speed allowed by the user's API tier. The deal count (264) remained stable during testing because the backfiller was clearing a backlog of unprofitable deals, but the processing pipeline itself is fully functional and responsive.
