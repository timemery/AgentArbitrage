# Fix Backfill Slowness & Token Starvation

**Date:** 2026-02-04
**Status:** SUCCESS
**Files Modified:** 
- `keepa_deals/backfiller.py`
- `keepa_deals/token_manager.py`
- `tests/test_backfill_performance.py` (New)

## Overview
The system was experiencing stalled deal collection (stuck at 62 deals) and "lugubrious" (extremely slow) backfill processing. Diagnostics indicated that while the `Backfiller` task was running (lock held), it was barely processing data.

Two distinct but compounding issues were identified:
1.  **Redundant Throttling:** The `backfiller.py` script contained a hardcoded `time.sleep(60)` after every chunk of 20 deals. This limited processing to a maximum of 20 deals per minute, regardless of available API tokens.
2.  **Token Starvation (Livelock):** The `TokenManager`'s recovery logic was overly conservative. When waiting for tokens, it calculated a target of `Threshold + Cost` (e.g., 80 + 100 = 180). However, the concurrent `Upserter` task runs every minute and consumes tokens as soon as they reach ~50, preventing the balance from ever accumulating to 180. This caused the Backfiller to wait indefinitely.

## Challenges & Diagnosis
*   **Misleading "Healthy" Status:** Standard diagnostics showed healthy services and active locks, masking the fact that the Backfiller was essentially doing nothing (waiting or sleeping).
*   **Invisible Livelock:** The "Insufficient tokens" warning in logs showed `Target: 185` while the current balance hovered at `40`. This gap was the smoking gun: the system was stuck waiting for a condition (185 tokens) that was physically impossible to reach under the current load.
*   **Double Throttling:** The `TokenManager` already correctly calculates wait times based on the refill rate (5 tokens/sec). The additional `sleep(60)` in the backfill loop was a legacy safeguard that had become a performance anchor.

## Solutions Implemented

### 1. Throughput Optimization (`keepa_deals/backfiller.py`)
Removed the hardcoded 60-second sleep.
*   **Old:** `time.sleep(60)` after every chunk.
*   **New:** `time.sleep(1)` (safety buffer).
*   **Impact:** The Backfiller now runs at the maximum speed allowed by the Keepa API token bucket (managed dynamically by `TokenManager`), drastically increasing potential throughput.

### 2. Starvation Fix (`keepa_deals/token_manager.py`)
Updated the `_wait_for_tokens` logic to align with the "Controlled Deficit" strategy.
*   **Old Logic:** Wait until `Balance >= Threshold + Cost`. (e.g., Wait for 180).
*   **New Logic:** Wait until `Balance >= Threshold`. (e.g., Wait for 80).
*   **Impact:** This allows the Backfiller to resume processing much sooner. By checking the *starting* balance against the threshold (and allowing the cost to drive the balance negative), we effectively utilize the Keepa API's deficit allowance, preventing the Upserter from starving the Backfiller.

## Verification
*   **Unit Test:** Created `tests/test_backfill_performance.py` which mocks the API and asserts that `time.sleep(60)` is never called, confirming the bottleneck removal.
*   **Diagnostics:** Post-deployment diagnostics showed:
    *   No "Insufficient tokens" warnings.
    *   Active "Priority Pass" logs (`Balance: 25.00`), proving the deficit logic is working.
    *   Immediate lock acquisition and processing start.

## Key Learnings
*   **Trust the TokenManager:** Centralized rate limiting is superior to distributed hardcoded sleeps.
*   **Deficits are Features:** In systems with "bursty" costs (like heavy backfills), strictly enforcing positive balances reduces throughput. Controlled deficits are essential for performance.
*   **Livelocks > Deadlocks:** A system that is "technically running" (waiting for resources) is often harder to diagnose than one that is deadlocked. Always check if the *wait condition* is actually achievable.
