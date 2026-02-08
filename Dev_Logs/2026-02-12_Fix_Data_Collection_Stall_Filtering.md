# Fix Data Collection Stall by Filtering Unprofitable Deals Early

**Date:** 2026-02-12
**Status:** SUCCESS
**Files Modified:** `keepa_deals/backfiller.py`

## Problem Overview
The system was experiencing a perceived "stall" in data collection, with the deal count remaining stagnant at 264 for an extended period. This was caused by the system spending its limited token budget (5 tokens/min) on "heavy fetches" (20 tokens) for deals that were ultimately unprofitable and rejected. This inefficiency meant the system was only processing ~0.25 deals/minute, creating a massive backlog.

## Diagnosis
*   **Architecture vs. Logic:** While the "Two-Stage Fetch" architecture (Peek Strategy) was implemented on Feb 7th, the *filtering logic* within it was a placeholder that accepted all candidates. This meant the system was still paying full price (20 tokens) to reject bad deals.
*   **Verification:** Running `Diagnostics/deep_dive_verification.py` on a sample ASIN (1455616133) confirmed that the system was correctly calculating profit and rejecting the deal due to a negative margin ($-5.79). The "stall" was simply the time taken to process a large volume of similarly unprofitable inventory.

## Solution Implemented

### 1. Implement `check_peek_viability` Heuristic
*   **File:** `keepa_deals/backfiller.py`
*   **Logic:** Replaced the permissive placeholder with a strict heuristic filter that analyzes the cheap (2-token) "peek" stats data before committing to a heavy fetch.
*   **Filtering Criteria:**
    *   **Absolute Price Floor:** Reject if estimated sell price < $12.00 (Fees make profit impossible).
    *   **Negative Spread:** Reject if Buy Price > (Sell Price * 1.1).
    *   **Gross ROI:** Reject if Gross ROI < 20%.

### 2. Impact
*   **Cost Reduction:** The cost to reject a "junk" deal drops from **20 tokens** to **2 tokens**.
*   **Throughput Increase:** This effectively increases the scanning speed for unprofitable inventory by **~10x**.
*   **Result:** The system can now churn through the backlog of bad data much faster, increasing the probability of finding and displaying profitable deals.

## Verification
*   **Unit Tests:** Created and ran `Diagnostics/verify_peek_filter.py` to confirm the logic correctly filters out low-ROI and negative-margin deals while accepting high-potential candidates.
*   **Deep Dive:** Confirmed that valid but unprofitable deals are correctly identified and handled.
