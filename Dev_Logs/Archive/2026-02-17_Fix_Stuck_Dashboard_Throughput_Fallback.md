# Dev Log: Fix Stuck Dashboard & Throughput Optimization
**Date:** 2026-02-17
**Author:** Jules (AI Agent)
**Task:** Resolve "Stuck Dashboard" (Deal count stagnant at 185) and "Dwindling Deals".

## Overview
The user reported that the dashboard deal count was stuck at 185 for hours, despite the database containing more records. Diagnostic reports revealed a "Mismatch" between the database count and the API count, as well as an extremely high rejection rate (93%) and a "stalled" ingestion pipeline (Celery worker repeatedly pausing for "Recharge Mode").

The investigation identified three distinct root causes:
1.  **Token Starvation:** The ingestion pipeline was overly conservative, reserving 5 tokens per "Peek" (light check) when the actual cost was ~1-2. On a low-tier Keepa plan (5 tokens/min), this forced the system into a "Recharge Mode" loop, processing only ~30 deals/hour.
2.  **High Rejection Rate (Fragile Data):** Many potential deals had sparse sales history (1-2 events). The strict "XAI Reasonableness Check" was rejecting these as "unreasonable" due to lack of context, resulting in a 93% failure rate for collected items.
3.  **Diagnostic Confusion:** The diagnostic tool (`comprehensive_diag.py`) used a loose filter (`Margin >= 0`) while the Dashboard API used strict filters (`Profit > 0`, Data Complete), creating a "Mismatch" report that eroded user trust.

## Challenges
*   **Token Economics:** Balancing throughput against the risk of Keepa API lockouts (Hard Limit -200) required precise calibration of reservation costs. Over-reservation protects the deficit but stalls the pipeline; under-reservation causes API errors.
*   **Safety vs. Yield:** Increasing yield by accepting sparse data carries the risk of "bad prices". We had to leverage the existing "Amazon Ceiling" logic (90% of New Price) to safely relax the XAI checks for fallback items.
*   **Git Hygiene:** Runtime state files (`xai_cache.json`, `xai_token_state.json`) were inadvertently tracked in git, causing potential merge conflicts.

## Solutions Implemented

### 1. Throughput Optimization (`keepa_deals/smart_ingestor.py`)
*   **Reduced Peek Reservation:** Lowered the token reservation for the "Peek" stage from **5 to 2** tokens per ASIN. The `fetch_current_stats_batch` call with `history=0` is cheap; reserving 5 was overly pessimistic.
*   **Increased Batch Size:** Increased the dynamic batch size for low-refill environments (< 10/min) from **5 to 15**.
    *   *Result:* With a cost of ~2 tokens/item, a batch of 15 costs ~30 tokens, fitting comfortably within the "Burst Threshold" of 40 tokens. This effectively **triples** the ingestion speed for low-tier plans.

### 2. Yield Improvement (`keepa_deals/stable_calculations.py`)
*   **Expanded Fallback Logic:** Increased `MIN_SALES_FOR_ANALYSIS` from **1 to 3**.
    *   *Effect:* Items with only 1 or 2 inferred sales are now classified as "sparse" and forced into the **Keepa Stats Fallback** path (`avg365` of Used offers).
    *   *Safety:* This path explicitly **SKIPS** the strict XAI Reasonableness Check (preventing false negatives) but remains protected by the **Amazon Ceiling** logic (preventing unrealistically high prices).

### 3. Diagnostic Alignment (`Diagnostics/comprehensive_diag.py`)
*   **Strict Filtering:** Updated the diagnostic SQL query to match the Dashboard API exactly:
    ```sql
    WHERE "Profit" > 0 AND "List_at" IS NOT NULL ...
    ```
    *   *Result:* The "Mismatch" error is resolved. The diagnostic now correctly reports that "Hidden" (incomplete) deals are distinct from "Visible" deals.

### 4. Git Hygiene
*   Removed `xai_cache.json` and `xai_token_state.json` from the repository tracking to prevent runtime state pollution.

## Outcome
**Status:** SUCCESS

*   **Ingestion Unblocked:** The Smart Ingestor can now process larger batches (15 items) without triggering immediate pauses, smoothing out the "Recharge Mode" cycle.
*   **Yield Increased:** Fragile deals (1-2 sales) are no longer rejected by XAI but are captured as "Silver Standard" (Estimated) deals, protected by the Amazon price ceiling.
*   **Confusion Resolved:** The diagnostic reports now accurately reflect the system state, confirming that "Stuck at 185" was a correct reflection of valid inventory, not a data sync failure.
