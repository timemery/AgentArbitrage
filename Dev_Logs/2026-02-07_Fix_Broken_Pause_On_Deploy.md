# Fix Broken "Pause on Deploy" Feature (2026-02-07)

## Problem
The user reported that the "Pause Feature" (Recharge Mode) was not triggering on deploy, causing the system to get stuck in a low-throughput state ("stuck at 275 deals").
Analysis revealed that while the `TokenManager` has logic to respect a "Recharge Mode" flag in Redis, the deployment script (`deploy_update.sh`) was **never actually setting this flag**.
This meant the system would restart, see > 20 tokens (e.g., 50), and immediately start processing small batches, never hitting the low watermark (< 20) required to trigger an automatic recharge. This resulted in a "livelock" where the system consumed tokens as fast as they refilled (5/min), preventing the high-efficiency "Burst Mode" from ever activating.

## Solution
1.  **Force Pause on Deploy:**
    -   Created `Diagnostics/force_pause.py`: A script that explicitly sets `keepa_recharge_mode_active = 1` in Redis.
    -   Updated `deploy_update.sh`: Added a step to run `force_pause.py` *before* starting the Celery workers.
    -   **Result:** Every deploy now forces the system to wait until 280 tokens are available before processing any deals.

2.  **Improved Diagnostics:**
    -   Created `Diagnostics/check_pause_status.py`: Inspects Redis for token count, refill rate, and the "Recharge Mode" flag.
    -   Updated `Diagnostics/run_suite.sh`: Includes this new check in the standard report.
    -   **Result:** Users can now see exactly *why* the system is paused (e.g., "Waiting for tokens to reach 280") and track progress.

## Verification
-   Verified `force_pause.py` correctly sets the Redis key.
-   Verified `TokenManager` correctly enters a wait loop when the key is set and tokens < 280.
-   Verified `TokenManager` correctly clears the key and resumes once tokens >= 280.

## Key Takeaway
For low-tier Keepa plans (5 tokens/min), "Burst Mode" is the only efficient way to operate. Relying on automatic low-watermark triggers is insufficient because the system can hover just above the watermark indefinitely. **We must force the recharge cycle on every restart.**
