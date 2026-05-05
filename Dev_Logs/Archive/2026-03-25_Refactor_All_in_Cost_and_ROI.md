# Dev Log: Refactor All-in Cost to Exclude Amazon Fees for Accurate ROI
**Date:** 2026-03-25

## Overview
The user reported that the `All-in Cost` displayed on the dashboard for a specific textbook (ASIN 0520009274) was extraordinarily high ($239) relative to the actual "Price Now" ($37.97). This inflated `All-in Cost` artificially deflated the dynamically calculated Return on Investment (ROI) to around 419%, masking the true profitability (which was closer to 2000%). The task was to audit the mathematical calculations in `keepa_deals/business_calculations.py`, correct the definition of `All-in Cost`, adjust the cascading formulas, and update the associated documentation.

## Investigation & Challenges
1.  **Circular Definition:** The legacy `calculate_all_in_cost` function correctly aggregated `Price Now`, Tax, Prep Fee, Shipping, FBA Fee, and the Referral Fee (which was calculated based on the *List at* price). While mathematically accurate for determining final `Profit`, injecting post-sale Amazon revenue deductions into the upfront `All-in Cost` bucket severely distorted the ROI denominator.
2.  **Cascading Equation Breakage:** Removing `Total AMZ fees` from `All-in Cost` meant that `calculate_profit_and_margin` and `calculate_min_listing_price` also had to be refactored to explicitly accept Amazon fees as independent variables, rather than assuming they were already bundled inside `all_in_cost`.
3.  **Circular Minimum Price Algebra:** The legacy `calculate_min_listing_price` simply divided `All-in Cost` by `(1 - markup)`. Because `All-in Cost` historically included a referral fee based on a *predicted* `List at` price, the minimum floor calculation suffered from circular logic. 
4.  **Database Integration Danger:** A critical challenge arose during the refactoring of `processing.py` and `recalculator.py`. Initial drafts attempted to explicitly save the newly separated `Total_AMZ_fees` into the database dictionaries. Because this column did not exist in the underlying SQLite `deals` schema, any manual `UPDATE` query (such as those heavily utilized by `recalculator.py`) would have triggered a fatal `sqlite3.OperationalError` and crashed the system.
5.  **Test Suite Fragility:** Modifying the signature of core business calculation functions immediately broke several tests. More problematically, the tests `test_stale_deal_rescue.py` and `test_simple_task_logic.py` were tightly coupled to either brittle `PropertyMock` overrides of `REFILL_RATE_PER_MINUTE` or entirely decommissioned modules (`simple_task`).

## Actions Taken
1.  **Refactored `calculate_all_in_cost`:** Modified `keepa_deals/business_calculations.py` so that `All-in Cost` now strictly reflects out-of-pocket acquisition capital (`Price Now` + Tax + Prep Fee + Shipping). FBA and Referral fees were entirely stripped out.
2.  **Refactored `calculate_profit_and_margin`:** Updated the signature to accept `amz_fees`. `Profit` is now correctly modeled as `List at - All-in Cost - amz_fees`.
3.  **Refactored `calculate_min_listing_price`:** Re-derived the floor pricing algebra natively to eliminate circular dependencies: `(All-in Cost + FBA Fee) / (1 - (Default Markup % / 100) - (Referral Fee % / 100))`.
4.  **Updated Processors:** Modified both `_process_single_deal` and `_process_lightweight_update` in `keepa_deals/processing.py` to extract, calculate, and pass `Total AMZ fees` separately to the downstream functions without injecting non-existent columns into the `row_data.update()` DB operations.
5.  **Updated Recalculator:** Modified `keepa_deals/recalculator.py` to accurately reproduce this split logic. Added a critical `isinstance(list_at_price, (int, float))` safety check before applying the referral fee percentage to prevent `TypeError` crashes against string placeholders like `"Too New"`.
6.  **Cleaned Up Tests:** 
    - Permanently deleted `test_simple_task_logic.py` (testing non-existent code).
    - Permanently deleted `test_stale_deal_rescue.py` (legacy/brittle mocks as agreed).
    - Updated mocks in all other calculation-dependent tests (e.g. `test_stable_calculations.py`) to pass cleanly against the new signatures and the previously removed Keepa Stats fallback logic.
7.  **Documentation Update:** Rewrote the `Business & Financial Metrics` section of `Documentation/Data_Logic.md` to explicitly state why Amazon fees are purposefully omitted from `All-in Cost`, providing clear reasoning for both developers and accountants.

## Result
The task was highly successful. The dashboard will now accurately reflect the dramatically lower upfront capital required (`All-in Cost`), and the dynamically calculated ROI will correctly soar (e.g., 400% -> 2000%+) to accurately represent the incredible cash-on-cash leverage of finding high-margin FBA inventory spreads. All corresponding unit tests pass.
