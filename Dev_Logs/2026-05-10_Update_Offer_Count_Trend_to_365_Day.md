# Dev Log: Update Offer Count Trend Comparison to 365-Day Window

**Date:** 2026-05-10
**Task Title:** Prime Picks Pass 1: Switch Offer-Trend Comparison to 365-Day Window

## Overview
The goal of this task was to update the `get_offer_count_trend_from_flat` function in `keepa_deals/new_analytics.py` to compare the current used offer count against the 365-day average instead of the 30-day average. The Pass 1 filter was previously dropping 0 candidates because the `Used_Offer_Count_30_days_avg` column in the database is intentionally left `NULL` to save on Keepa API token costs and storage, resulting in no trend signal being calculated. 

## Challenges
- Ensuring that the correct column `Used_Offer_Count_365_days_avg` was used.
- Updating variable names (`avg30_str` to `avg365_str` and `avg30` to `avg365`) and docstrings to reflect the logic change accurately without altering the core functionality.
- Verifying the implementation without disrupting production, as the dev environment (sandbox) acts differently from the live environment (Agent Arbitrage deployed on Apache at agentarbitrage.co).

## Implementation Details
1. **File Modified:** `keepa_deals/new_analytics.py`
2. **Function Modified:** `get_offer_count_trend_from_flat(deal, logger=None)`
3. **Changes Made:**
    - Changed the extraction logic from `deal.get('Used_Offer_Count_30_days_avg', '')` to `deal.get('Used_Offer_Count_365_days_avg', '')`.
    - Renamed variables `avg30_str` and `avg30` to `avg365_str` and `avg365` for clarity.
    - Updated the docstring to explicitly state that it uses the 365-day average for comparison.
4. **Validation:** Executed `./run_tests.sh` to ensure all core tests passed and no regressions were introduced.

## Deployment Notes
- **Important:** Since testing was performed in a sandbox environment, production verification is still required by the user.
- **Verification Steps for Production:** 
  1. Trigger the Prime Picks refresh from the admin Deals page.
  2. Run `Diagnostics/extract_pass2_reasoning.py` against `celery_worker.log`.
  3. Verify via `grep "Pass 1 Filter" celery_worker.log | tail -5` that the summary line shows non-zero dropped candidates and dramatically reduced "no trend signal" counts.

## Outcome
The task was successfully completed in the local dev environment, with all tests passing. The updated logic will allow Pass 1 to correctly drop candidates with rising offers and weak sales velocity when deployed to production.