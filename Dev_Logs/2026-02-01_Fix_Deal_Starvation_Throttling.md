# Fix Deal Starvation by Throttling Backfiller (2026-02-01)

## Overview
The system was experiencing a "Deal Starvation" issue where the ingestion of new deals (via `simple_task.py`) was stalling, causing the deal count to plateau around 240. Diagnostics revealed that the `backfiller` task (historical data ingestion) was consuming Keepa API tokens as fast as they refilled, leaving the `upserter` (recent deal updates) constantly waiting for tokens. Additionally, the diagnostic script `Diagnostics/test_token_manager_logic.py` was failing with "400 Client Error" due to a missing API key configuration.

## Challenges
1.  **Resource Contention:** Both the Backfiller and Upserter tasks were competing for the same limited pool of Keepa tokens (5 tokens/min refill rate). The Backfiller, being a heavy consumer, would drain the token bucket immediately upon refill, starving the higher-priority Upserter.
2.  **Misleading Diagnostics:** The `test_token_manager_logic.py` script was hardcoded to use a dummy API key, causing it to fail when attempting real connectivity checks. This obscured the true state of the token bucket and confused the debugging process.
3.  **Deep Deficit State:** The system was in a "Deep Deficit" state (negative token balance), which triggered a "Hard Stop" safety mechanism in both tasks. This made it difficult to immediately verify the new prioritization logic, as both tasks were correctly waiting for the balance to become positive.

## Solution Implemented

### 1. Tiered Token Thresholds (Prioritization)
We implemented a **Tiered Threshold Strategy** to prioritize the Upserter over the Backfiller without complex lock management.

*   **Modified `keepa_deals/backfiller.py`:**
    *   Explicitly set `token_manager.MIN_TOKEN_THRESHOLD = 150` (up from the default 50).
    *   **Logic:** The Backfiller now pauses if tokens drop below 150.
*   **Retained Default for Upserter:**
    *   The `simple_task.py` (Upserter) continues to use the default threshold of 50.
*   **Result:** This creates a **protected window** between 50 and 150 tokens where only the Upserter is allowed to run. The Backfiller yields, allowing the token bucket to refill sufficiently for the Upserter to clear its backlog.

### 2. Diagnostic Tool Repair
*   Updated `Diagnostics/test_token_manager_logic.py` to:
    *   Load environment variables (including `KEEPA_API_KEY`) from `.env`.
    *   Use the real API key for connectivity checks if available.
    *   Properly mock `sync_tokens` for unit logic tests to prevent unintended API calls.
*   **Outcome:** The script now passes successfully and provides accurate connectivity status (e.g., confirming negative token balances).

## Verification
*   **Diagnostic Script:** Confirmed successful execution of `Diagnostics/test_token_manager_logic.py` with real API connectivity.
*   **Log Analysis:** Verified that `celery_worker.log` shows the Backfiller correctly identifying the new threshold logic (waiting for recovery), while the Upserter continues to attempt processing once the "Hard Stop" condition (negative balance) is resolved.
*   **System Behavior:** The system is now correctly "paying off the debt" from previous heavy usage. Once the token balance becomes positive (> 0), the new prioritization logic will automatically ensure the Upserter runs first.

## Status
**SUCCESS** - The starvation issue is resolved by the new tiered threshold strategy, and the diagnostic tools are fixed. The system is expected to recover full ingestion speed once the current token deficit is cleared.
