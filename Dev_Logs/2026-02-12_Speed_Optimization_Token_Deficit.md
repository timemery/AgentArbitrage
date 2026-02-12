# Dev Log: Speed Optimization and Token Deficit Utilization

**Date:** 2026-02-12
**Task:** Investigate and Improve Data Collection Speed (Deficit Utilization)
**Status:** SUCCESS

## Overview
The user reported that the dashboard was "stalled" with only ~15 deals collected after 30 minutes. The system was deemed too conservative in its token usage, especially given the low refill rate (5 tokens/min) and the available "deficit" buffer (-120 tokens) allowed by Keepa. The goal was to optimize the `TokenManager` and `Smart Ingestor` to utilize this deficit aggressively and reduce the idle time caused by the "Safety Pause".

## Key Changes

### 1. Token Strategy Optimization (`keepa_deals/token_manager.py`)
-   **Lowered `MIN_TOKEN_THRESHOLD`:** Reduced from `20` to `1`.
    -   *Why:* Previously, the system stopped processing when it had 20 tokens left, leaving potential capacity unused. Setting it to 1 allows the system to initiate a request even with a tiny positive balance. Since a batch request costs ~30-110 tokens, this pushes the balance into the negative (deficit), effectively using the "overdraft" allowance.
-   **Lowered `BURST_THRESHOLD`:** Reduced from `80` (or `150` in initial plan) to `40` for low-refill environments (< 10/min).
    -   *Why:* Waiting for 80 tokens at 5/min takes ~16 minutes of idle time. Waiting for 150 takes ~30 minutes. Lowering this to 40 reduces the recovery pause to ~8 minutes, making the system feel much more responsive and "alive" without sacrificing safety (40 tokens is enough for a short burst).

### 2. Ingestor Throughput (`keepa_deals/smart_ingestor.py`)
-   **Increased `MAX_ASINS_PER_BATCH`:** Increased from `2` to `5` and removed logic that throttled batch sizes when refill rates were low.
    -   *Why:* Larger batches are more efficient. By grouping 5 ASINs, we push a larger "deficit dip" (e.g., spending 100 tokens when we only have 5), maximizing the utility of the allowed overdraft.
-   **Increased `current_max_deals`:** Raised from `20` to `50` for low-refill rates.
    -   *Why:* Matches the expanded token budget provided by the deficit strategy.

### 3. Diagnostic Tooling
-   **New Tool:** Created `Diagnostics/estimate_ingestion_time.py`.
    -   *Function:* Simulates the ingestion process for 10,000 deals using the new V3 logic (Peek vs Commit costs).
    -   *Insights:* Confirms that the token bucket will never reach 300 under this strategy (which is intentional to maximize throughput) and provides time estimates (e.g., ~5.5 days for 10k deals with a 10% survivor rate).
-   **Updated:** `Diagnostics/check_pause_status.py` and `verify_deficit.py` updated to reflect the new thresholds.

## Challenges Faced
-   **Token Math:** Balancing the desire for speed with the hard constraint of 5 tokens/min. The realization was that "filling the bucket" (reaching 300) is actually inefficient because it implies idle time. The optimal strategy for a low-refill environment is to *empty* the bucket as fast as possible and then pulse (work/wait/work).
-   **Test Environment:** The sandbox lacked a running Redis instance, requiring manual installation and startup to verify the token manager logic.

## Results
-   **Outcome:** The system successfully resumed ingestion immediately after deployment (as the new threshold of 40 was lower than the available 48 tokens).
-   **Impact:** The "Stalled" state is resolved. The system will now cycle more frequently (8 min waits vs 30 min waits) and process larger batches, utilizing the full capacity of the Keepa API account.
-   **Verification:** Verified via `verify_deficit.py` tests and live diagnostics confirming the new "Waiting for 40" status.
