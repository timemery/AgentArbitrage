# Task Plan: Reduce "Missing List at" Rejection Rate

## Objective
Reduce the 98.5% rejection rate caused by "Missing List at" by enhancing the "inferred sale" logic and improving XAI prompt context. The goal is to accurately calculate a safe "List at" price for more items without providing unrealistic prices.

## Findings from Investigation
1.  **Strict XAI Validation:** The current XAI prompt lacks context (e.g., Sales Rank, Binding, Image), causing it to reject valid prices (e.g., rejecting $56.97 for a generic-sounding title).
2.  **Strict "Sale Event" Window:** The current logic requires a rank drop within 168 hours (7 days) of an offer drop. "Near miss" logs show sales occurring just outside this window (e.g., 45-52 hours late).
3.  **Lack of High-Velocity Logic:** High-velocity items (Rank < 20k) often don't show clear "offer drops" or "rank drops" because the graph is too smooth, leading to 0 inferred sales despite high `monthlySold` counts.

## Proposed Plan

### 1. Improve XAI Prompt Context
**Goal:** Give the AI enough information to make an informed decision about price reasonableness.
- **Action:** Update `_query_xai_for_reasonableness` in `keepa_deals/stable_calculations.py` to include:
    - **Sales Rank (Current & 90-day avg):** To show popularity.
    - **Binding:** (Hardcover/Paperback) to justify price.
    - **Page Count:** (If available) to distinguish pamphlets from textbooks.
    - **Image URL:** (If possible/relevant) or at least more product metadata.
    - **"Monthly Sold" (if available):** To prove demand.

### 2. Relax "Sale Event" Window
**Goal:** Capture sales that are slightly delayed in reporting or slower to manifest in rank changes.
- **Action:** Increase `search_window` in `infer_sale_events` from 168 hours (7 days) to **240 hours (10 days)**.
- **Action:** Monitor "Near Miss" logs after this change to see if it captures the missed events.

### 3. Implement "Monthly Sold" Fallback
**Goal:** Provide a valid "List at" price for high-velocity items where specific "drops" are hard to detect.
- **Action:** Map the `monthlySold` field from Keepa API (likely in `product['stats']` or `product` root) to a usable variable.
- **Action:** Create a fallback calculation in `get_list_at_price`:
    - **Condition:** If `sane_sales` count is low (e.g., < 3) AND `monthlySold` > 20 (arbitrary threshold, needs tuning).
    - **Fallback Price:** Use `Used - 90 days avg` (or `Buy Box Used - 90 days avg`) as the candidate "List at" price.
    - **Validation:** Send this fallback price to XAI for reasonableness checking just like the Peak Price.

### 4. Refine Outlier Rejection
**Goal:** Ensure we don't aggressively filter out valid high prices for textbooks.
- **Action:** Review `symmetrical` outlier rejection. Ensure it's not removing the *only* valid sales if they happen to be higher than the "lowball" offers.

### 5. Amazon Price Ceiling Logic
**Goal:** Establish a hard ceiling for inferred Used prices based on Amazon's own "New" pricing, ensuring we never predict a Used sale price higher than what Amazon sells it for New (minus a margin).
- **Concept:** Amazon's New price acts as a natural cap. A Used book is highly unlikely to sell for more than Amazon's New price. To be conservative, we assume the maximum safe Used price is ~10% below Amazon's New price.
- **Data Points:**
    - `Amazon - Current`
    - `Amazon - 180 days avg.`
    - `Amazon - 365 days avg.`
- **Logic:**
    1.  Collect all valid, positive prices from the three Amazon data points above.
    2.  Determine the **minimum** of these prices to find the most conservative baseline.
    3.  Calculate `Ceiling Price = Minimum Amazon Price * 0.90` (representing 10% below).
    4.  **Capping:** If the calculated `List at` price (derived from Peak Season Mode or Monthly Sold Fallback) exceeds this `Ceiling Price`, cap it at the `Ceiling Price`.
    5.  This logic is applied *before* the final XAI reasonableness check.

## Verification Plan
1.  **Re-run Debug Script:** Use a script similar to `Diagnostics/debug_rejection.py` to test the new logic on the previously rejected ASINs (e.g., `0615307655`).
2.  **Backfill Test:** Run a small backfill (e.g., 50 items) and check the rejection rate stats using `Diagnostics/count_stats.sh`.
3.  **XAI Log Check:** Verify in logs that XAI is receiving the expanded context and giving more accurate "Yes/No" responses.
