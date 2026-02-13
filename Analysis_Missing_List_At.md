# Analysis: High Rejection Rate (Missing 'List at')

**Date:** 2026-02-05
**Status:** Diagnosis Complete

## 1. Problem Overview
The deal processing pipeline is experiencing a **24.08% rejection rate** (46 out of 191 deals rejected).
-   **100% of rejections** (46 deals) are due to "Missing 'List at'".
-   **0% of rejections** are due to "Missing '1yr Avg'".

## 2. Root Cause Analysis

### A. Fallback Logic Check
-   **Hypothesis:** Is a fallback mechanism (e.g., using `avg90` when sales are missing) causing the issue?
-   **Verification:**
    -   I reviewed `keepa_deals/stable_calculations.py` and confirmed that the "High Velocity / Sparse Data Fallback" (which used `monthlySold` and `avg90`) has been **removed**. The code explicitly comments this out.
    -   I performed a codebase-wide search for `fallback`, `monthlySold`, and `avg90`. While `avg90` is used in `stable_products.py` for *display* metrics (like "Sales Rank - 90 days avg"), it is **not** used to calculate the "List at" price in the core inference logic.
-   **Conclusion:** The rejections are **not** caused by the previously identified "Zombie Listing" fallback logic or any other hidden fallback mechanism.

### B. "Missing List at" Logic Trace
Since `1yr Avg` is successfully calculated for these deals, we know:
1.  **Sales Exist:** `infer_sale_events` found valid sales in the last 365 days.
2.  **Peak Price Calculated:** Since sales exist, a "Peak Season" and its corresponding "Mode Price" (`peak_price_mode_cents`) are mathematically calculable.

The `get_list_at_price` function only returns `None` (causing rejection) if `peak_price_mode_cents` is set to `-1`.
The code sets `peak_price_mode_cents = -1` in exactly one scenario after calculation:

```python
    is_reasonable = _query_xai_for_reasonableness(...)
    if not is_reasonable:
        # If XAI deems the price unreasonable, we invalidate it by setting it to -1.
        peak_price_mode_cents = -1
```

### C. The Diagnosis
The high rejection rate is caused by the **AI Reasonableness Check** (`_query_xai_for_reasonableness`) returning `False`.
This means the AI believes the calculated "List at" price is unreasonable for the book (e.g., price is too high, or AI is too conservative).

## 3. Proposed Fix: Task Description

**Task Title:** Optimize AI Price Validation to Reduce False Rejections

**Context:**
The system is rejecting ~24% of deals because the AI Reasonableness Check flags the "List at" price as invalid. We need to determine if these are "True Positives" (saving us from bad deals) or "False Positives" (rejecting good deals), and adjust the logic accordingly.

**Steps to Execute:**

1.  **Enhanced Logging (Diagnosis):**
    -   Modify `keepa_deals/stable_calculations.py` to log the specific inputs and output of the AI check when it fails.
    -   Log: `ASIN`, `Title`, `Calculated Price`, `AI Response (False)`.
    -   *Goal:* See exactly *what* prices are being rejected.

2.  **Audit Rejections (Analysis):**
    -   Run `python3 keepa_deals/simple_task.py` (or a targeted script) to process a batch of deals.
    -   Inspect the logs to review the rejected items.
    -   **Decision Point:**
        -   **Scenario A (Zombie Prices):** If the rejected prices are absurdly high (e.g., $400 for a generic paperback), the inference engine is picking up "Zombie" offers. **Action:** Implement a pre-AI filter (e.g., `Reject if Price > 4 * 1yr_Avg`) to filter these cheaply without wasting AI tokens.
        -   **Scenario B (Strict AI):** If the prices look reasonable (e.g., $45 for a Textbook) but AI says "No", the AI is hallucinating or too strict. **Action:** Tune the AI prompt (e.g., add "You are an Arbitrage Advisor, slight premiums are expected...") or increase the temperature slightly.

3.  **Option C: Extended History & Trend Analysis (Strategic Enhancement):**
    -   **Concept:** Use a 3-year history to provide a stronger "Reasonableness Signal" to the AI or as a mathematical validation layer.
    -   **Implementation Steps:**
        -   **Verify Data:** Check `keepa_query.json` and `keepa_api.py` to ensure the `dateRange` parameter (currently "4") supports fetching 3 years (approx 1000 days) of history.
        -   **Extend Window:** Update `infer_sale_events` in `stable_calculations.py` to look back 3 years instead of 2 (`timedelta(days=1095)`).
        -   **Calculate Trend:** Implement a `3yr_Trend` metric (Slope of price over 3 years).
        -   **Logic Application:**
            -   If `List At` > `Price Now` BUT `3yr_Trend` is **Significantly Down**, flag as "Unreasonable" (Mathematical Rejection).
            -   Inject `3yr_Avg` and `3yr_Trend` into the AI prompt (e.g., "The price has been trending DOWN for 3 years, is a peak price of $X still reasonable?").
    -   **Benefit:** This uses hard data to catch "falling knife" scenarios that might currently look like good deals based on a short-term blip, or validate high prices that are supported by a long-term upward trend.

4.  **Implement Optimizations:**
    -   Apply the chosen fix (Pre-filter, Prompt Tuning, or Extended Trend).
    -   Verify the rejection rate drops below 10-15% while maintaining data quality.

5.  **Verify & Cleanup:**
    -   Ensure no "fallback" data logic is reintroduced.
    -   Remove the temporary debug logging.
