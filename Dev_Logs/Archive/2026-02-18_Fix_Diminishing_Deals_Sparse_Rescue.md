# Dev Log: Fix Diminishing Deals & Sparse Sales Rescue

**Date:** 2026-02-18
**Author:** Jules (AI Agent)
**Task:** Investigate and fix the issue of "diminishing deals" where the dashboard deal count was dropping despite valid inventory being scanned.

## 1. Overview
The user reported that the dashboard deal count was dropping (from 183 to 172) and "stuck". The goal was to identify why potentially valid deals were being rejected or hidden and to fix the pipeline to capture them ("widen the net").

## 2. Challenges & Root Causes

### A. The "Sparse Data" Trap
The system recently increased `MIN_SALES_FOR_ANALYSIS` from 1 to 3 to improve data quality. Deals with 1 or 2 sales were forced into a "Keepa Stats Fallback" path (using `avg365` of Used offers).
*   **Problem:** For many low-velocity or new items, Keepa statistical averages (like `avg365`) are `None` or missing, even if the system successfully inferred 1 or 2 sales events from the raw history.
*   **Result:** The fallback failed, returning a price of `-1`, causing the deal to be rejected as "Dead Inventory". This was the primary cause of valid deals disappearing.

### B. Narrow Condition Checking
The fallback logic only checked standard "Used" conditions (Indices 2, 19, 20, 21, 22).
*   **Problem:** Many books are listed specifically as "Collectible" (Indices 23, 24, 25, 26). If a book had *only* Collectible offers and no standard Used history, it was being ignored.

### C. Runtime Crash (TypeError)
A regression was found in `stable_calculations.py`:
```python
if len(avg90) > 21 and avg90[21] > 0: ...
```
*   **Problem:** Keepa frequently returns explicit `None` values in the stats arrays. Comparing `None > 0` raises a `TypeError`, causing the worker to crash on that task and the deal to be lost.

### D. Diagnostic Misreporting
The `diagnose_hidden_deals.py` script reported 100% of deals as "Hidden" because it failed to parse currency strings (e.g., "$138.41") from the database `List_at` column, falsely flagging them as invalid (`<= 0`).

## 3. Solutions Implemented

### A. Sparse Sales Rescue (`keepa_deals/stable_calculations.py`)
Implemented a new rescue mechanism within `analyze_sales_performance`.
*   **Logic:** If the "Keepa Stats Fallback" fails (no averages found), the system now checks if there are *any* valid inferred sales (1 or 2 events).
*   **Action:** If sales exist, it calculates the **Median** of those sales prices and uses it as the reference price.
*   **Safety:** The source is flagged as `Inferred Sales (Sparse)`, and the XAI Reasonableness Check is **skipped** for this source to prevent the AI from rejecting it due to lack of historical context.

### B. Widening the Net (Collectible Support)
Updated the fallback candidate search to include all "Collectible" sub-conditions:
*   Collectible - Like New (Index 23)
*   Collectible - Very Good (Index 24)
*   Collectible - Good (Index 25)
*   Collectible - Acceptable (Index 26)

### C. Crash Fix
Added strict type checking to all array accesses:
```python
if len(avg90) > 21 and avg90[21] is not None and avg90[21] > 0: ...
```

### D. Diagnostic Fix
Updated `Diagnostics/diagnose_hidden_deals.py` to strip currency symbols (`$`, `,`) and safely cast strings to floats before performing logic checks.

## 4. Verification
*   **Unit Tests:** Created `tests/test_stable_calculations_sparse_rescue.py` which verified:
    *   `test_sparse_sales_rescue`: Deals with 2 sales and missing stats are now accepted (Median used).
    *   `test_collectible_fallback`: Deals with only Collectible history are accepted.
    *   `test_missing_stats_type_error_fix`: Code no longer crashes on `None` values.
*   **Diagnostics:** Running the fixed diagnostic tool confirmed that the "Hidden" deals were primarily due to Profit <= 0 (expected persistence behavior) and that "List_at Missing" count is stable.

## 5. Outcome
**Status: SUCCESS**
The system now robustly handles sparse data and collectible-only items, preventing the "diminishing deals" phenomenon. The diagnostic tools are accurate, and the worker is protected against crashes from malformed Keepa data.
