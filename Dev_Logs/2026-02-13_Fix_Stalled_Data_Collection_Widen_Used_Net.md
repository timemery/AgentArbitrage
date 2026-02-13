# Dev Log: Fix Stalled Data Collection (Widen Used Net)

**Date:** 2026-02-13
**Task:** Investigate and Fix Stalled Data Collection (91% Rejection Rate)
**Status:** SUCCESS

## 1. Overview
The user reported that the dashboard deal count was stuck at 86 for several days, despite the system running. Diagnostics revealed a **91% rejection rate**, with the primary cause being "Missing 'List at'". This indicated that while deals were being fetched, they were failing the detailed analysis stage because the system could not determine a valid reference price.

## 2. Root Cause Analysis
-   **Diagnosis:** The "Peek" stage (initial filter) was too loose, and the "Commit" stage (detailed analysis) was too strict, creating a mismatch.
    -   **Peek Filter:** `check_peek_viability` was allowing deals that had *only* New or Amazon price history (but no Used history) to pass.
    -   **Commit Logic:** The downstream logic (`analyze_sales_performance`) strictly required "Used" (Index 2) or "Used - Good" (Index 21) history to calculate a "List at" price. It treated New/Amazon history as invalid for used books.
-   **Result:** The system would spend tokens fetching full details for items with only New history, only to reject them immediately because it couldn't calculate a "Used" reference price. This wasted tokens and stalled the accumulation of valid deals.

## 3. Solution Implemented
The strategy was to "widen the net" for valid used books while strictly excluding New-only items to align with the user's data accuracy requirements.

### A. Widen the Net (Include Sub-Conditions)
Modified `keepa_deals/smart_ingestor.py`, `keepa_deals/stable_calculations.py`, and `keepa_deals/new_analytics.py` to recognize **ALL** standard Used sub-conditions as valid price history sources:
-   **Index 2:** Used
-   **Index 19:** Used - Like New
-   **Index 20:** Used - Very Good
-   **Index 21:** Used - Good
-   **Index 22:** Used - Acceptable

Previously, the system ignored indices 19, 20, and 22. Items that *only* had history in these specific sub-conditions (common for certain books) were being rejected.

### B. Strict Exclusion of New/Amazon
Updated `check_peek_viability` in `keepa_deals/smart_ingestor.py` to **explicitly ignore** New (Index 1) and Amazon (Index 0) price history.
-   **Why:** The user confirmed that "inferred sale price" must reflect used book value. Using New/Amazon prices as a proxy is inaccurate.
-   **Outcome:** Deals that *only* have New/Amazon history are now rejected at the very first step (Peek), saving tokens for valid used book candidates.

## 4. Challenges & Verification
-   **Challenge:** Ensuring the filter logic exactly matched the processing logic to prevent token waste.
-   **Verification:** Created a diagnostic script `test_peek_filter_strictness.py` which confirmed:
    -   **Case A (New Only):** REJECTED (Correct).
    -   **Case B (Used):** ACCEPTED (Correct).
    -   **Case E (Used - Acceptable Only):** ACCEPTED (Correct - previously failed).

## 5. Conclusion
The system now correctly targets *any* valid used book (regardless of sub-condition) while filtering out irrelevant New-only inventory. This should resolve the 90% rejection rate and allow the deal count to grow beyond 86.
