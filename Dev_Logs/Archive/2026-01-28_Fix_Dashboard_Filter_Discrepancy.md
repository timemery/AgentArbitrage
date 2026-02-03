# Fix Dashboard Filter Discrepancy

**Date:** 2026-01-28
**Author:** Jules (AI Agent)
**Status:** Success

## 1. Task Overview
The user reported a discrepancy between the deal counts displayed in the Web UI ("931 Deals Found") and the "Dashboard Visible" count reported by the `Diagnostics/comprehensive_diag.py` script (746 Deals). The goal was to investigate this mismatch and reconcile the numbers.

## 2. Investigation & Root Cause
*   **Diagnostic Logic:** The `comprehensive_diag.py` script explicitly defined "Dashboard Visible" as deals with `Margin >= 0`. It reported 746 such deals out of a total of 931 in the database.
*   **Web UI Logic (Previous):** The dashboard sliders for "Min. Margin" and "Min. Profit" defaulted to a value of `0`, which was visually labeled as "Any".
*   **The Bug:** The JavaScript logic in `dashboard.html` (`getFilters()`) treated the value `0` as a wildcard ("Any") and explicitly removed the filter from the API request (`if (val !== '0')`).
*   **Result:** On initial load, the dashboard sent *no filters* to the backend, causing it to return all 931 records, including 185 deals with negative margins or profits. The diagnostic script, however, was filtering these out, leading to the count mismatch.

## 3. Challenges
*   **Frontend-Backend Logic Gap:** The backend API (`/api/deals`) correctly supported `margin_gte=0`, but the frontend code was hardcoded to suppress this parameter when the slider was at zero.
*   **Environment Stability:** Initial attempts to verify the fix were hampered by network connectivity issues in the sandbox environment when running Playwright, requiring careful debugging of the test script setup.

## 4. Resolution
I modified `templates/dashboard.html` to enforce strict filtering for profitable deals by default.

### Changes:
1.  **Updated Slider Labels:** Changed the label for the `0` position on the Profit and Margin sliders from "Any" to **"$0+"** and **"0%+"** respectively.
2.  **Updated Filter Logic:** Modified the `getFilters()` JavaScript function to remove the check that ignored zero values.
    *   *Before:* `if (profitMargin && profitMargin !== '0') ...`
    *   *After:* `if (profitMargin !== '') ...`
    *   This ensures that when the slider is at 0, the parameter `margin_gte=0` is sent to the backend.
3.  **Updated Reset Logic:** The "Reset" button now resets these sliders to `0` (and effectively ">= 0") rather than "Any".

## 5. Outcome
*   **Verified:** The frontend now defaults to showing only profitable deals (Margin >= 0).
*   **Consistent:** The "Deals Found" count on the dashboard now matches the "Dashboard Visible" count (746) reported by the diagnostic tools.
*   **Improved UX:** Users are no longer shown unprofitable deals by default, which aligns better with the goal of arbitrage.
