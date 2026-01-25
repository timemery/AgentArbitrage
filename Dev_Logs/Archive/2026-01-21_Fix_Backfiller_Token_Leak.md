# Fix Backfiller Token Leak & Infinite Loop
**Date:** 2026-01-21
**Status:** SUCCESS

## Overview
The system experienced a critical issue where the "Backfiller" (specifically the `update_recent_deals` task) was consuming excessive tokens, driving the balance deep into the negative (e.g., -205 tokens) without successfully processing any deals. This "token leak" starved other critical tasks, such as the main `backfill_deals` process, causing the dashboard to stagnate.

The root cause was identified as an unbounded pagination loop in `keepa_deals/simple_task.py`. While the task checked for tokens *before* starting, it did not re-check the token balance *during* the execution of the loop. If the "Watermark" logic failed to find an older deal (or if the API returned a large number of "new" pages), the task would continue fetching pages indefinitely, ignoring the token deficit.

## Challenges
*   **Identifying the "Leak":** The logs showed `update_recent_deals` claiming to skip execution due to low tokens, which was confusing. However, closer inspection revealed that once a task *did* start (when tokens were > 20), it would never stop until it finished pagination, regardless of how many tokens it burned in the process.
*   **Controlled Deficit Compatibility:** The fix had to respect the system's "Controlled Deficit" strategy, which allows dipping into negative balance for efficiency. A naive fix (waiting for full 300 refill) would have slowed down the system. The solution needed to stop the *current* runaway run but allow the system to resume quickly once the buffer (20 tokens) was restored.

## Resolution
1.  **Internal Token Checks:**
    *   **File:** `keepa_deals/simple_task.py`
    *   **Action:** Added `if not token_manager.has_enough_tokens(5): break` inside both the main pagination loop (Step 2) and the product batch processing loop (Step 3).
    *   **Effect:** This forces the task to exit gracefully as soon as the token balance dips below the safety threshold, saving whatever progress has been made (upserting deals) before terminating.

2.  **Safety Limits:**
    *   **File:** `keepa_deals/simple_task.py`
    *   **Action:** Added a constant `MAX_PAGES_PER_RUN = 50` and a check `if page >= MAX_PAGES_PER_RUN: break`.
    *   **Effect:** This acts as a "circuit breaker" to prevent infinite loops even if tokens are available, ensuring no single task execution runs for an unreasonable amount of time.

## Technical Details
*   The `update_recent_deals` task is now robust against "infinite pagination" scenarios.
*   The fix does *not* require a database reset or a full token refill. The system will naturally recover on the next scheduled run.
*   **Verification:** Unit tests were created to confirm that the loop breaks correctly when tokens are mocked to run out, and when the page limit is reached.
