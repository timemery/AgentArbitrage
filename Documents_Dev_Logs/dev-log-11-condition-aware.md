# Dev Log 11: Condition-Aware Restriction Checks & High-Volume Rejection Analysis

## Overview
This sprint focused on two primary objectives: improving the accuracy of the "Check Restrictions" feature by making it condition-aware, and investigating data throughput issues. We successfully implemented the condition mapping logic and deployed a new diagnostic tool that revealed a critical insight: **98.5% of potential deals are being rejected** due to pricing validation failures.

## Critical Implementations

### 1. Condition-Aware SP-API Calls
- **Problem:** The previous restriction check was "generic," often returning broad restrictions without specific "Apply to Sell" links because Amazon didn't know which condition (e.g., "Used - Very Good") we intended to sell.
- **Solution:**
    - **Mapping:** Implemented `map_condition_to_sp_api` in `keepa_deals/amazon_sp_api.py`. This function translates internal database values (e.g., "Used - Like New", "2") into the strict enum format required by Amazon (e.g., `used_like_new`).
    - **Batching Update:** Modified `check_all_restrictions_for_user` in `keepa_deals/sp_api_tasks.py` to query the `Condition` column from the database alongside the ASIN.
    - **API Integration:** Updated `check_restrictions` to accept a dictionary of items (ASIN + Condition) and append the `conditionType` parameter to the API request.

### 2. Protective Comments (The Stability Pact)
- Added explicit "DO NOT CHANGE" comments to `keepa_deals/backfiller.py` and `keepa_deals/simple_task.py`.
- **Protected Values:**
    - `DEALS_PER_CHUNK = 20`: Essential for allowing token bucket refills.
    - Token Buffer = 20: Prevents the upserter from starving the backfiller.
    - Seller Fetching: strictly "single seller" fetch, prohibiting regressions to "all sellers".

### 3. Diagnostic Tooling (`count_stats.sh`)
- Created `Diagnostics/count_stats.sh` to provide immediate visibility into data pipeline health.
- **Function:** Queries the SQLite database for active deal counts and parses `celery_worker.log` to categorize rejection reasons.
- **Key Finding:** Running this script on the production server revealed a **Rejection Rate of 87.59%**.
    - **98.5%** of rejections were due to **"Missing List at"**.
    - This indicates the system is finding deals but discarding them because the "Safe List Price" calculation (or its AI validation) is failing or being too conservative.

## Known Issues / Next Steps

### The "Spinning Gated Column"
- **Symptom:** The user reported that 19 deals on the dashboard had "spinning" indicators in the Gated column for over 2 hours.
- **Diagnosis:** This implies the `check_all_restrictions_for_user` task is either stalled, failing silently, or the results are not being saved/read correctly.
- **Hypothesis:**
    1.  **Task Crash:** The worker might have crashed on a specific condition mapping edge case.
    2.  **Locking:** The database might be locked.
    3.  **Frontend/Backend Mismatch:** The dashboard might be expecting a different status value.
- **Action:** See `NEXT_TASK.md` for specific debugging steps.

## Technical Details
- **Files Modified:**
    - `keepa_deals/amazon_sp_api.py`
    - `keepa_deals/sp_api_tasks.py`
    - `keepa_deals/backfiller.py`
    - `keepa_deals/simple_task.py`
- **New Files:**
    - `Diagnostics/count_stats.sh`
