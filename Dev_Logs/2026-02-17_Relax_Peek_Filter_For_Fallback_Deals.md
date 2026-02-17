# Dev Log: Relax Peek Filter for Fallback Deals

**Date:** 2026-02-17
**Task:** Relax Smart Ingestor Peek Filter to Allow Low-Velocity Deals

## Overview
The system was experiencing a decline in deal volume ("diminishing deals") despite recent updates intended to support "Silver Standard" or "Keepa Stats Fallback" logic for low-velocity items. The goal was to identify why these items were not being processed and fix the bottleneck to allow more deals through the pipeline.

## Challenges
*   **High Rejection Rate:** Diagnostics showed a 56.2% rejection rate at the "Peek Filter" stage in `smart_ingestor.py`.
*   **Silent filtering:** The "Silver Standard" logic in `stable_calculations.py` (designed to accept items with sparse data but valid price history) was never being triggered for many items because they were being rejected *before* reaching that stage.
*   **Token Constraints:** The system was operating under a significant token deficit (-70 tokens), meaning that any solution had to be careful about increasing API load, even though relaxing filters naturally increases load.

## Root Cause Analysis
The `check_peek_viability` function in `keepa_deals/smart_ingestor.py` acts as an initial gatekeeper to save tokens on obviously bad deals. It had a hardcoded threshold:
```python
# Threshold: 4 drops/year (~1 per quarter).
if drops365 != -1 and drops365 < 4:
    return False
```
This logic explicitly rejected any item with fewer than 4 sales rank drops per year. However, the "Silver Standard" fallback logic is specifically designed to handle items with very low sales velocity (e.g., 1-3 sales per year) where strict "Inferred Sales" logic fails but price history is stable. By rejecting these items at the gate, the ingestor was starving the downstream logic of candidates.

## Solution
I modified `keepa_deals/smart_ingestor.py` to lower the `salesRankDrops365` threshold from 4 to 1.
*   **New Logic:**
    ```python
    # UPDATE (Feb 2026): Reduced to 1 drop/year to allow "Silver Standard" fallback candidates (1-3 sales)
    # to pass through. 0 drops is still rejected as "Dead Inventory".
    if drops365 != -1 and drops365 < 1:
        return False
    ```
*   **Impact:** Items with 1, 2, or 3 annual sales drops now pass the Peek Filter and proceed to the "Commit" stage, where `stable_calculations.py` can apply the "Silver Standard" fallback logic (checking price consistency without requiring high sales velocity).
*   **Dead Inventory:** Items with 0 drops are still rejected to prevent wasting tokens on dead stock.

## Verification
*   **Unit Testing:** Created `tests/test_peek_logic.py` to verify the new behavior.
    *   `test_peek_drops_4_passes`: PASSED (Baseline)
    *   `test_peek_drops_3_should_pass_target`: PASSED (New behavior)
    *   `test_peek_drops_1_should_pass_target`: PASSED (New behavior)
    *   `test_peek_drops_0_should_fail`: PASSED (Dead Inventory check maintained)
    *   `test_peek_drops_unknown_passes`: PASSED (Safety fallback)
*   **Regression Testing:** Verified that `tests/test_smart_ingestor_batching.py` and other core tests still pass.

## Outcome
The task was successful. The code changes have been deployed and verified.
*   **Note on Deal Volume:** As of the time of this log, the dashboard deal count (183) has not yet spiked because the system is in "Recharge Mode" due to low Keepa tokens. The increase in deal volume is expected to occur gradually over the next 24-48 hours as the ingestor processes new batches with the relaxed criteria.
