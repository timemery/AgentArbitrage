# Fix: Wildly High Profits in Fallback Logic (Suspiciously High Check)

**Date:** 2026-02-18
**Author:** Agent Jules
**Task:** Investigate and fix "Wildly High Profits" in deals using Keepa Stats Fallback.

## Overview
Users reported that certain deals on the dashboard were showing "wildly high" profit estimates (e.g., $1400 List Price for a $40 item), leading to unrealistic ROI calculations.

Investigation revealed that these deals were low-velocity items using the **"Keepa Stats Fallback"** (Silver Standard) logic. This logic attempts to estimate a price when no recent sales exist by looking at historical averages (`stats.avg365`). To prevent false negatives for these "sparse data" items, the system had been configured to **SKIP** the AI Reasonableness Check.

The issue arose because the fallback logic selects the *maximum* price from a range of Used/Collectible conditions. In cases of "Market Manipulation" (where sellers list items at exorbitant prices during off-seasons) or extreme Collectible listings, the fallback price became inflated. Because the AI check was skipped, these inflated prices were accepted as valid "List Prices".

## Resolution: "Suspiciously High Fallback" Check

To address this without breaking the functionality for legitimate "Silver Standard" deals, I introduced a targeted sanity check in `keepa_deals/stable_calculations.py`.

### The Logic
We introduced a **Ratio Threshold** of **3.0 (300%)**.
The system now calculates the ratio between the **Estimated List Price** (Fallback) and the **Current Used Price**.

1.  **If Ratio <= 3.0:** The deal is considered "Normal". The system continues to **SKIP** the AI check (preserving the original intent of the Silver Standard).
2.  **If Ratio > 3.0:** The deal is flagged as **"Suspiciously High"**. The system **FORCES** the AI Reasonableness Check to run.

### Example
*   **Scenario:** A book is selling for $40. The fallback logic finds a historical "Collectible" average of $1400.
*   **Ratio:** $1400 / $40 = **35x**.
*   **Action:** The system flags this as suspicious. It asks the AI: *"Is a price of $1400 reasonable for this book?"*
*   **Outcome:** The AI answers "No", and the price is invalidated (set to -1), preventing the bad deal from appearing on the dashboard.

## Challenges Faced
*   **Balancing Act:** The main challenge was filtering out the "bad" high prices without accidentally rejecting valid "good" prices for seasonal textbooks (which can legitimately sell for 3-4x their off-season lows). The 3x threshold combined with the AI's contextual understanding provides a robust filter that catches egregious outliers while allowing reasonable fluctuations.
*   **Data Integrity:** We had to ensure the check handled cases where `current_used_price` was missing (`-1` or `None`) without crashing. In such cases, the check defaults to "Not Suspicious" (False) to avoid blocking data flow.

## Verification
I created a reproduction script (`tests/test_wild_profit_check.py`) that simulated a deal with a massive price disparity ($1400 vs $40). The test confirmed that:
1.  The system correctly identified the fallback source.
2.  It calculated the ratio and flagged it as suspicious.
3.  It successfully **forced** the AI check (which was previously skipped).
4.  The price was invalidated upon AI rejection.

## Outcome
Successful. The system now has a safeguard against manipulated or outlier fallback data while maintaining the utility of the Silver Standard for legitimate inventory.
