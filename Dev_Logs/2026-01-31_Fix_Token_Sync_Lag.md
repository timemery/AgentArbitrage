# Fix Token Sync Lag (Smart Polling) - Dev Log

**Date:** 2026-01-31
**Task:** Fix the synchronization lag where the application's local token count drifted from the actual Keepa dashboard, causing unnecessary delays.
**Status:** Success

## 1. Overview
The user reported a discrepancy between the application logs and the Keepa dashboard.
*   **Logs:** `Successfully retrieved token status: ... 'tokensLeft': 9`
*   **Dashboard:** `Currently available tokens: 19`

This issue caused the system to enter a "Recovery Mode" sleep (e.g., waiting 10 minutes) based on the outdated or pessimistic local estimate of 9 tokens, while in reality, the account had already recovered to 19 tokens. This "Blind Sleeping" behavior reduced the system's overall throughput and responsiveness.

## 2. Challenges Faced

### The "Blind Sleep" Problem
The root cause was the implementation of the `request_permission_for_call` method in `TokenManager`.
*   **Old Logic:**
    1.  Calculate tokens needed to reach the safe threshold.
    2.  Calculate wait time (e.g., 600 seconds).
    3.  `time.sleep(600)` (Sleep for the full duration).
*   **The Flaw:** During this 600-second sleep, the application was completely blind to the outside world. If the user upgraded their plan (increasing the refill rate) or if another concurrent worker finished its task (freeing up the global token bucket), the sleeping worker would not know until it woke up 10 minutes later.

### Process Isolation (Drift)
Because Celery workers run in separate processes, they maintain their own local instances of `TokenManager`. While we implemented a "Sync-Before-Wait" check previously, it only synced *once* at the start of the wait. It did not account for changes *during* the wait.

## 3. Solution Implemented

We replaced the single long sleep with a **Smart Polling Loop** in `keepa_deals/token_manager.py`.

### The New Logic:
1.  **Chunked Sleeping:** Instead of sleeping for the full calculated duration (e.g., 600s), the system now loops and sleeps in short **30-second intervals**.
2.  **Continuous Synchronization:** At the end of every 30-second chunk, the worker calls `sync_tokens()`.
    *   **Cost:** 0 Tokens (Keepa's `/token` endpoint is free/cheap and included in response headers).
    *   **Benefit:** This updates the local `self.tokens` and `self.REFILL_RATE_PER_MINUTE` with the *authoritative* values from the Keepa server.
3.  **Dynamic Recalculation:**
    *   After every sync, the code checks: `if self.tokens >= recovery_target: break`. This allows the worker to resume *immediately* if the tokens recover faster than expected.
    *   If still low, it recalculates the `remaining_wait` based on the *current* refill rate. This ensures that if the rate drops (or increases), the wait time adapts dynamically.

### Code Snippet (Simplified):
```python
while remaining_wait > 0:
    sleep_chunk = min(remaining_wait, 30)
    time.sleep(sleep_chunk)

    self.sync_tokens() # Authoritative Update

    if self.tokens >= recovery_target:
         logger.info("Tokens recovered sufficiently. Resuming early.")
         break

    # Recalculate wait based on new data
    new_wait = math.ceil((needed / self.REFILL_RATE_PER_MINUTE) * 60)
    remaining_wait = new_wait
```

## 4. Verification
*   **Unit Testing:** Created a test case (`tests/test_token_manager_v2.py`) where the mocked API simulated a drastic drop in refill rate during the sleep. The test confirmed that the loop correctly extended the wait time instead of timing out prematurely.
*   **User Confirmation:** The user confirmed that the logs and dashboard are now in sync ("They are now in sync").

## 5. Key Learnings
*   **Never Sleep Blindly:** In a distributed or rate-limited system, long sleeps should always be broken up into polling intervals to check for state changes.
*   **Authoritative Source:** Always prefer the server's truth (API response) over local estimation logic when the cost to check is low/zero.
