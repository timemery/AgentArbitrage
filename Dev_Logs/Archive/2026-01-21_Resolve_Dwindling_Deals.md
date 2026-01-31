# Resolve Dwindling Deals & Fix Zombie Listings
**Date:** 2026-01-21
**Status:** SUCCESS

## Overview
The system was experiencing a "Dwindling Deals" phenomenon where the active deal count would steadily decrease over time, eventually reaching near-zero, despite the Backfiller running continuously. Investigation revealed that the system was rejecting approximately 95% of processed deals.

The root cause was identified as a specific "High-Velocity" fallback mechanism in the price calculation logic. This fallback was erroneously assigning high "Used" prices to items that were only selling as "New", creating "Zombie Listings" (items that look like deals but have no actual used sales). These listings were subsequently—and correctly—rejected by the downstream AI Reasonableness Check, but the effort wasted on processing them prevented legitimate deals from entering the system.

## Challenges
*   **The "Zombie" Phenomenon:** Identifying why items with high sales velocity were failing price checks. It turned out that `monthlySold` aggregates *all* conditions (New + Used). A book selling 100 copies/month as "New" at $50 would trigger the fallback if it had a stale "Used" listing at $400.
*   **The "High Velocity" Fallback:** The code in `stable_calculations.py` contained a block intended to handle sparse data: `if monthlySold > 20: use avg90_used`. This simplistic heuristic proved fatal for data quality, as it decoupled the price estimation from actual *confirmed* sales events.
*   **Environment Instability:** Previous attempts to debug this were hampered by environment issues (missing dependencies like `pandas` or `httpx` in the test runner), highlighting the need for robust dependency management in the dev environment.

## Resolution
1.  **Removed the Dangerous Fallback:**
    *   **File:** `keepa_deals/stable_calculations.py`
    *   **Action:** Completely removed the `if monthlySold > 20` block in `analyze_sales_performance`.
    *   **New Logic:** If `peak_season_prices` (derived from confirmed inferred sales) is empty, the function now returns `-1` immediately. The system no longer guesses prices. If we can't prove a sale happened at a specific price, we do not list the item.

2.  **Tightened Keepa Query:**
    *   **File:** `keepa_query.json`
    *   **Action:** Updated `salesRankRange` from `[100,000, 5,000,000]` to `[50,000, 1,000,000]`.
    *   **Rationale:** Removing the "long tail" of low-velocity items (Rank > 1M) reduces the noise entering the pipeline and focuses resources on items more likely to have verifiable sales data.

3.  **Verification:**
    *   Added a regression test `tests/test_stable_calculations.py` that simulates a "Zombie Product" and asserts that the system returns `-1` instead of a fallback price.

## Technical Details / Lessons Learned
*   **Accuracy > Completeness:** In an arbitrage system, it is far better to miss a potential deal (False Negative) than to import a bad deal (False Positive). Fallback logic that populates missing data with "averages" or "estimates" without a confirming signal (like a sales rank drop) is a liability.
*   **Inferred Sales are King:** The only source of truth for "List at" price should be the `infer_sale_events` function (Rank Drop + Offer Drop). If that function returns nothing, the item should be considered "Price Unknown" and rejected.
*   **AI as a Filter, Not a Fix:** The AI Reasonableness Check was working correctly by rejecting these bad prices. The problem was that we were feeding it garbage to begin with. Fixing the upstream data source reduces AI costs and increases system throughput.
