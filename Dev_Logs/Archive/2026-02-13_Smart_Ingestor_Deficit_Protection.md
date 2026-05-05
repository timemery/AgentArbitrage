# 2026-02-13: Smart Ingestor Deficit Protection & Dynamic Batching

## Task Overview
The objective was to investigate and resolve an issue where the `Smart Ingestor` was consuming Keepa API tokens beyond the allowable deficit of -200 (reaching -253), leading to API lockouts and stalled data collection ("stuck at 86 deals"). The goal was to enforce a strict deficit limit and optimize the ingestion process to prevent "token starvation" for accounts with lower refill rates.

## Challenges Faced

1.  **Unbounded Deficit Consumption**: The existing `TokenManager` allowed operations to proceed as long as the *starting* balance was positive (even +1), without checking if the *resulting* balance would exceed safe limits. Large batch requests (e.g., 50 ASINs * 5 tokens = 250 tokens) could instantly push a small positive balance into a deep, unsafe deficit (e.g., +5 - 250 = -245).
2.  **"All-or-Nothing" Batching**: The `Smart Ingestor` used a fixed `SCAN_BATCH_SIZE` of 50. For users with low refill rates (< 20/min), the cost of a single batch (250 tokens) was often higher than the available burst capacity, causing the system to perpetually block or fail to acquire enough tokens to run even a single cycle.
3.  **Refill Rate Sensitivity**: The system was optimized for high-throughput accounts and didn't adapt well to slower refill rates, leading to long "Recharge Mode" pauses where no data was collected.

## Solutions Implemented

### 1. Enforced Deficit Limit (`keepa_deals/token_manager.py`)
Introduced a `MAX_DEFICIT` constant set to **-180**.
-   **Logic**: Before approving any API request, the `TokenManager` now calculates the *projected* balance (`current_tokens - estimated_cost`).
-   **Action**: If the projected balance would fall below -180, the request is **blocked** (raises `TokenRechargeError` or sleeps), forcing the system to wait for a refill.
-   **Why -180?**: This provides a safety buffer of 20 tokens before hitting Keepa's hard limit of -200, accounting for potential concurrency variances or floating-point drift.

### 2. Dynamic Batch Sizing (`keepa_deals/smart_ingestor.py`)
Implemented adaptive batch sizing based on the account's refill rate.
-   **High Rate (>= 20/min)**: Defaults to `SCAN_BATCH_SIZE = 50` (Standard optimization for speed).
-   **Low Rate (< 20/min)**: Automatically reduces `SCAN_BATCH_SIZE` to **20**.
-   **Benefit**: A batch of 20 ASINs costs ~100 tokens. This is much easier for a low-tier account to "afford" (accumulate) than a 250-token batch, significantly reducing the "time to first fetch" and preventing the system from locking up in "Recharge Mode" for extended periods.

## Outcome
**Success.**
-   **Deficit Control**: Verified via reproduction scripts that the system now correctly blocks requests that would push the balance below -180.
-   **Operational Stability**: The system no longer hits the -200 lockout.
-   **Data Flow**: By reducing the batch size for the test environment (refill rate 5/min), the ingestor can now successfully process smaller chunks of data more frequently, rather than stalling indefinitely waiting for a massive token bucket that never fills.

## Technical Details for Future Reference
-   **File(s) Modified**: `keepa_deals/token_manager.py`, `keepa_deals/smart_ingestor.py`.
-   **Key Constant**: `MAX_DEFICIT = -180` (TokenManager).
-   **Key Logic**: `if token_manager.REFILL_RATE_PER_MINUTE < 20: current_batch_size = 20` (SmartIngestor).
