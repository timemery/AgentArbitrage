# Task: Refine Pass 1 Offer-Trend Logic with Velocity-Aware Override
Date: 2026-05-09

## Overview
The goal of this task was to replace a soft offer-trend penalty with a velocity-aware hard filter during the "Smart Floor" (Pass 1) of the Prime Picks evaluation process. Previously, candidates with rising offers were penalized with a soft multiplier. However, analysis of Pass 2 reasoning indicated that the LLM was still consistently rejecting these candidates because the multiplier wasn't strong enough to drop them from the top 20 candidates, and that the LLM only specifically objected to rising offers when paired with weak sales velocity. 

Additionally, the previous logic incorrectly prioritized new condition offer counts as a measure of competition over used condition offer counts. Given that the Prime Picks strategy specifically sources for "Used - Like New" deals, the correct measure of competition is used condition offers.

## Challenges Faced
1.  **Refining the Logic without Loosening Thresholds:** The primary challenge was strictly applying the logic to evaluate offer trend *and* velocity without inadvertently changing other scoring aspects.
2.  **Structuring the Loop Iteration:** Because the old logic modified candidate scores in place while constructing the top 20 list, adding a hard filter meant carefully constructing a separate list (`filtered_deals`) of eligible candidates that met the criteria to avoid sorting dropped candidates.
3.  **Deploying for Verification:** The full real-world impact on the Pass 2 selection ratio could not be verified in the local sandbox because testing relies directly on Live Keepa Data and querying the xAI API on actual active inventory, which requires a trigger on the production server.

## Actions Taken
1.  **Modified Configurable Thresholds:** 
    - Removed `PASS_1_OFFER_TREND_PENALTY_CAP = 0.5`.
    - Added `PASS_1_OFFER_TREND_RISING_THRESHOLD = 0.25` and `PASS_1_OFFER_TREND_VELOCITY_GATE = 100000` to `keepa_deals/prime_picks_task.py`.
2.  **Corrected Offer Count Fallback Chain:**
    - Refactored the fallback chain to prioritize used offers. The new order is: `Used_Offer_Count_30_days_avg` -> `Used_Offer_Count_180_days_avg` -> `New_Offer_Count_30_days_avg` -> `New_Offer_Count_180_days_avg`.
3.  **Implemented the Velocity-Aware Hard Filter:**
    - Constructed a loop to flag and drop candidates exceeding both the rising threshold (>25% trend) and velocity gate (>100,000 rank).
    - Preserved the existing `PASS_1_OFFER_TREND_BONUS_MULTIPLIER` for items with falling or stable offers.
4.  **Logging Enhancements:**
    - Implemented specific `INFO` level logs for each candidate dropped by the filter (`[Pass 1 Filter] Dropped ASIN=...`).
    - Added a summary log detailing the total number of candidates dropped out of the total pool.
5.  **Documentation:**
    - Provided manual testing instructions in `Dev_Logs/pass_1_velocity_filter_update.md` so that the admin can trigger a real-world pass 2 on the production server and analyze the ratio.

## Status: Success
The modifications were applied, testing the local suite showed all core unit tests passing securely, and the logic was updated successfully. The dev logs effectively documented the manual verification steps needed for the live deployment.