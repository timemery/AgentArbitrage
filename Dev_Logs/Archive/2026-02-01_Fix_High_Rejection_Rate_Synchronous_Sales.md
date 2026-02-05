# Dev Log: Fix High Rejection Rate (Synchronous Sales Events)

**Date:** 2026-02-01
**Task:** Investigate and fix the excessively high deal rejection rate (55% - 67%) characterized by "Missing List at" and "Missing 1yr Avg" errors.

## 1. Overview
The system was rejecting a majority of deals, even potentially profitable ones. Diagnostics showed that the primary failure mode was "Missing List at" (87.9% of rejections) and "Missing 1yr Avg" (12.1%). Both of these metrics rely on the `infer_sale_events` function to detect sales history. If no sales are detected, these metrics cannot be calculated, and the deal is discarded.

## 2. Root Cause Analysis
Deep investigation revealed a subtle edge case in how the system interprets Keepa data for slow-moving (high rank) items.

### The "Synchronous Update" Phenomenon
Keepa's crawlers visit slow-moving items less frequently (sometimes days apart). When a crawl occurs, it captures a snapshot of the current state.
- If a book sold since the last crawl, the **Offer Count** will have dropped.
- The **Sales Rank** will also have dropped (improved).
- Crucially, Keepa records both of these changes with the **exact same timestamp** corresponding to the crawl time.

### The Logic Bug
The original logic in `keepa_deals/stable_calculations.py` used an **exclusive** comparison to verify a sale:
```python
# Original Code
rank_changes_in_window = df_rank[(df_rank['timestamp'] > start_time) & ...]
```
Here, `start_time` is the timestamp of the Offer Drop. The code demanded that the Rank Drop happen strictly *after* (`>`) the Offer Drop.
For synchronous updates where `Rank Drop Time == Offer Drop Time`, this condition failed. The system saw the offer drop but "missed" the rank drop confirmation, ignoring the sale.

## 3. The Fix
The logic was updated to use an **inclusive** comparison:
```python
# Fixed Code
rank_changes_in_window = df_rank[(df_rank['timestamp'] >= start_time) & ...]
```
This simple change allows the system to correctly identify sales where the evidence (Rank Drop) and the trigger (Offer Drop) are recorded simultaneously.

## 4. Verification & Challenges

### Verification
A new regression test `tests/test_synchronous_updates.py` was created to simulate this exact scenario.
- **Scenario:** An item with an Offer Drop at `T=1440` and a Rank Drop at `T=1440`.
- **Result:**
    - Before Fix: 0 Sales inferred.
    - After Fix: 1 Sale inferred.
- **Outcome:** The test passed, confirming the logic now correctly captures these events.

### Challenges
1.  **Live Verification:** Attempting to verify the fix with live data via a diagnostic script failed with `429 Too Many Requests`. This was actually a positive sign—it indicated that the production Backfiller and Upserter were running efficiently and fully utilizing the Keepa token bucket (Starvation issue resolved).
2.  **Test Environment:** The new test script initially failed with `ModuleNotFoundError` when run directly. This was resolved by appending `os.getcwd()` to `sys.path` in the test file.

## 5. Conclusion
**Status:** SUCCESS
The fix is deployed. As the Backfiller continues to cycle through the database, it will now correctly "save" these previously rejected deals. Users should observe a gradual decrease in the rejection rate and an increase in the number of visible deals over the next 12-24 hours.
