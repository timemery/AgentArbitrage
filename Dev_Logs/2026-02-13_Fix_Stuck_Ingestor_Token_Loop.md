# Fix: Stuck Ingestor (Token Loop)
**Date:** 2026-02-13
**Author:** Jules

## Overview
The Smart Ingestor was stuck processing 86 deals for several days, refusing to fetch new deals despite the Celery task running every minute. Diagnostics revealed the `TokenManager` was trapped in a "Recharge Mode" loop with a perpetually negative token balance (e.g., `-79.0`), which never updated because the system believed 0 seconds had elapsed since the last refill.

## Root Cause Analysis
The issue stemmed from how the `TokenManager` initialized its `last_refill_timestamp`:
1.  **Initialization:** `self.last_refill_timestamp = time.time()` (current time) on every worker start.
2.  **Missing Redis Key:** If the Redis key `keepa_token_timestamp` was missing (e.g., due to a crash, eviction, or manual flush), the `TokenManager` relied on its local initialization.
3.  **Calculation Error:**
    *   `elapsed_time = time.time() - self.last_refill_timestamp`
    *   `elapsed_time = Now - Now = 0`
    *   `Refill = 0 * Rate = 0`
4.  **Deadlock:**
    *   The `TokenManager` read the *existing* negative token balance from Redis (e.g., `-79`).
    *   It added the calculated refill (`0`), resulting in a projected balance of `-79`.
    *   `should_skip_sync()` returned `True` because the projected balance was still critically low.
    *   The system skipped the API sync (which would have fixed the balance) and exited to "recharge," creating an infinite loop.

## The Fix
I modified `keepa_deals/token_manager.py` to initialize `self.last_refill_timestamp = 0`.

### Why this works:
1.  **Safety Default:** If the Redis timestamp is missing, the calculation becomes `elapsed_time = Now - 0`, resulting in a massive elapsed time (years).
2.  **Forced Refill:** The projected refill becomes huge, filling the bucket to `max_tokens` (300).
3.  **Triggered Sync:** `should_skip_sync()` now returns `False` (bucket full).
4.  **Self-Healing:** The system calls `sync_tokens()` on the Keepa API. The API response returns the *actual* token count (e.g., 17), which overwrites the local/Redis state, breaking the loop and restoring normal operation.

## Verification
*   **Reproduction:** Created `repro_stuck_ingestor.py` which successfully simulated the stuck state (tokens=-79, timestamp=None) and confirmed `should_skip_sync() == True`.
*   **Confirmation:** After applying the fix, the same script confirmed `should_skip_sync() == False`.
*   **Production:** Post-deployment diagnostics showed the token count recovering from `-79.0` to `17.0` and entering valid "Recharge Mode" (waiting for 40 tokens), proving the fix worked in the live environment.

## Outcome
**SUCCESS.** The system recovered automatically after deployment.
