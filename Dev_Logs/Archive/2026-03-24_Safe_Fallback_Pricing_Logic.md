# Fix: Safe Fallback Pricing Logic (Min instead of Max)

**Date:** 2026-03-24
**Author:** Agent Jules
**Status:** Success (Awaiting Data Collection)

## Overview
The user reported that the Deals Dashboard was frequently displaying "astronomical" or overly optimistic "List At" prices for certain deals, leading to unrealistic profit margins. The goal was to investigate the calculation logic—specifically the fallback mechanisms used when actual sales data is sparse—and theorize ways to ensure prices remain reasonable without unnecessarily eliminating deals from the database.

## Challenges & Investigation
1.  **The "Max" Fallback Problem:**
    The investigation revealed that when the primary algorithm (`infer_sale_events`) failed to find at least 3 confirmed sales drops within a 3-year window, the system triggered a "Keepa Stats Fallback." 
    This fallback gathered the 90-day and 365-day average prices for *all* "Used" and "Collectible" sub-conditions (indices 2, 19-26). Crucially, the code then set the `List At` price to the **`max(candidates)`**. 
    This meant a single, stubborn high listing for "Collectible - Like New" could dictate the expected sale price for a standard arbitrage flip, causing the astronomical profit estimates.

2.  **The Strict Policy vs. Token Limits Dilemma:**
    We theorized completely eliminating the fallback mechanism (the "Strict Inferred Only" policy), meaning any deal without 3 confirmed sales would be rejected (`List At = -1`).
    - *Impact:* Historical data showed ~64% of deals rely on fallbacks. Rejecting them would significantly slow down the accumulation of deals.
    - *Token Math:* Because the strict policy rejects deals at Stage 2 (costing 20 API tokens) instead of adding them to the dashboard for cheap Stage 3 maintenance (1 API token), the system would burn through its 5 tokens/min limit searching for the rare, perfect deals. The mathematical ceiling of ~500 deals wouldn't drop, but the *time* to reach that ceiling would increase dramatically.

## Solutions Implemented
We opted for a "Safe Fallback Compromise" rather than completely eliminating the fallback, preserving ingestion speed while fixing the mathematical skew.

1.  **Stripped Collectible Conditions:**
    Modified `analyze_sales_performance` in `keepa_deals/stable_calculations.py` to entirely ignore Keepa Stats for "Collectible" items (indices 23, 24, 25, 26). These rarely apply to standard FBA arbitrage and heavily skew data upward.

2.  **Switched from `max()` to `min()`:**
    Changed the final fallback price selection from `max(candidates)` to `min(candidates)`. When data is sparse, the system now recommends the *most conservative* historical average available among the standard "Used" conditions (e.g., Acceptable, Good, Very Good).

3.  **Amazon Ceiling Safety Net:**
    Confirmed that the universal Amazon Ceiling check (capping the `List At` price at 90% of the lowest available Amazon New price) remains active and correctly applies to these newly adjusted fallback prices.

4.  **Testing:**
    Updated `tests/test_stable_calculations.py` to assert that the `peak_price_mode_cents` correctly calculates the `min()` value (e.g., $350 instead of $400) when provided with fallback candidates. Tests pass successfully.

## Conclusion
The task was successful. The codebase now safely handles sparse data by defaulting to the most conservative historical price, rather than the most optimistic one. The database has been cleared, and the system is currently ingesting new data under these stricter, safer pricing rules.
