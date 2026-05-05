# Fix Diminishing Deals: Token Recharge Loop Resolution
**Date:** 2026-02-18
**Author:** Jules (AI Agent)
**Status:** SUCCESS

## Overview
The system was experiencing a "Diminishing Deals" issue where the total deal count was slowly decreasing (from 182 to 169) because the ingestion pipeline (`smart_ingestor`) was stalled. Despite running on schedule, the ingestor was failing to import new deals due to a persistent "Tokens critically low" state.

## Issue Analysis
The root cause was identified as a **Recharge Loop / Deadlock** in `keepa_deals/token_manager.py`.

1.  **Stale State:** The `TokenManager` uses Redis to store the current token count and timestamp. Due to previous interruptions or aggressive diagnostics, the Redis state became stale: tokens were negative (e.g., -65), but the timestamp was updated recently (or the system *thought* it was recent enough).
2.  **The Trap:** When `smart_ingestor` started, it called `token_manager.request_permission_for_call(5)`.
3.  **Wait Calculation:** The manager calculated a `wait_time` based on the negative tokens (-65) and the refill rate (5/min). The wait time was ~21 minutes (1260s).
4.  **Abort Logic:** Because the wait time was > 60 seconds, the manager raised a `TokenRechargeError` to avoid blocking the worker thread for too long.
5.  **The Loop:** The `smart_ingestor` caught this exception and exited immediately. Crucially, **it exited before performing a `sync_tokens()` call.**
6.  **Result:** The system never contacted the Keepa API to get the *actual* token count. The next run saw the same negative tokens in Redis, calculated the same long wait, and aborted again. The system was effectively blind to the fact that its tokens had actually refilled on the Keepa side.

## Solution Implemented
I modified `keepa_deals/token_manager.py` to add a "Last Resort" check inside `request_permission_for_call`:

- **Logic:** When the calculated `wait_time` exceeds 60 seconds (which would normally trigger an abort), the system now **Forces a Sync** first.
- **Action:** It calls `self.sync_tokens(force=True)`, which bypasses local throttling and fetches the authoritative token status directly from the Keepa API.
- **Recovery:**
    - If the API reveals that tokens have refilled (e.g., to 300), the system updates the local/Redis state, clears the "Recharge Mode" flag, and allows the task to proceed immediately.
    - If the API confirms tokens are *still* low, it recalculates the wait time. If it's still > 60s, it then raises the exception as before.

## Verification
A targeted diagnostic script `Diagnostics/verify_fix_recharge_loop.py` was created and run post-deployment.

**Results:**
- **Before Fix:** Redis tokens stuck at -65. Logs showed repeated "Recharge needed: 1260s. Exiting task."
- **After Fix:**
    - Logs showed: `Executing FORCE SYNC to verify state.`
    - Logs showed: `Burst threshold reached after Force Sync. Exiting Recharge Mode.`
    - Redis tokens updated to **35.0** (positive!).
    - Ingestion resumed (Deal timestamp started updating).

## Artifacts
- **Modified File:** `keepa_deals/token_manager.py`
- **New Diagnostic:** `Diagnostics/verify_fix_recharge_loop.py`
- **Tests:** `tests/test_smart_ingestor_batching.py` (Regression tested)

## Conclusion
The deadlock is broken. The system can now self-heal from stale token states by verifying with the API before giving up.
