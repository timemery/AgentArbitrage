# Fix Token Starvation & System Stall
**Date:** 2026-01-23
**Status:** PARTIAL SUCCESS (Logic fixed, monitoring ongoing)

## Overview
The system experienced a severe regression where the API token balance dropped to extreme negative values (e.g., -340), and deal collection completely stalled. Despite the `backfiller` seemingly running (logs showed "SP-API Restriction Check"), no new deals were appearing on the dashboard.

## Root Cause Analysis
1.  **Token Starvation (The "Regressed" 50 Batch Size):**
    *   The `update_recent_deals` task was configured with `MAX_ASINS_PER_BATCH = 50`.
    *   Fetching 3 years of history for 50 items costs ~1000 tokens.
    *   With a refill rate of 5 tokens/minute, this demand far outstripped supply, causing the bucket to crash into negative hundreds immediately upon execution.

2.  **Starvation Loop (The Entry Gate):**
    *   The task had a safety check: `if not has_enough_tokens(20): return`.
    *   Because the system was constantly hovering near 0-5 tokens due to other drains (or slow refill), the task would abort *before* it could run, never getting a chance to process even a small batch.

3.  **The "Ghost" Lock (System Stall):**
    *   The `backfiller` task had likely crashed or been killed previously but left its `backfill_deals_lock` in Redis.
    *   `simple_task` checks this lock and aborts if it exists (`Backfill task is running...`).
    *   The logs showed `check_all_restrictions_for_user` running, but this task *does not* hold the backfill lock. This confirmed that the lock was stale, effectively freezing the `simple_task` indefinitely.

## Resolution
### 1. Code Fixes (`simple_task.py`)
*   **Reduced Batch Size:** Lowered `MAX_ASINS_PER_BATCH` from 50 to **10**. This reduces the cost per batch to ~200 tokens, which is manageable.
*   **Blocking Wait Strategy:** Replaced the "check and abort" logic inside the loop with `token_manager.request_permission_for_call()`. This forces the task to *wait* (sleep) for tokens to refill rather than quitting, ensuring progress (albeit slow) is always made.
*   **Relaxed Entry Gate:** Lowered the initial check from 20 tokens to **5 tokens**. This breaks the starvation loop, allowing the task to start and rely on the internal blocking wait to handle the deficit.

### 2. Operational Fixes
*   **Stale Lock Clearing:** Provided a script (`clear_backfill_lock.py`) to manually remove the `backfill_deals_lock` from Redis, unblocking the `simple_task`.
*   **Documentation:** Added explicit comments in the code warning against increasing the batch size back to 50 without testing.

## Current Status
The code logic is sound and robust against token starvation. However, the system requires time to recover from the massive deficit and process the backlog of tasks (restriction checks). The user is monitoring the system overnight to see if data ingestion resumes naturally now that the locks and logic are fixed.
