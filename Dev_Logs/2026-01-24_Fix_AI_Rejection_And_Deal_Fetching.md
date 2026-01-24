# Fix AI Price Rejection and Deal Fetching Stalls
**Date:** 2026-01-24
**Status:** SUCCESS

## Overview
Addressed a critical issue where 100% of processed deals were being rejected with the error `Missing 'List at': (Could not determine a safe listing price or AI rejected it)`. Additionally, investigated and resolved a separate issue where the system's deal ingestion watermark was stuck in 2014, preventing the collection of new data.

## Challenges
1.  **False Positive AI Rejections:** The AI Reasonableness Check (powered by Grok) was rejecting valid peak-season prices for textbooks (e.g., a $150 book with a $45 yearly average) because the prompt lacked context about seasonal price variance. The AI interpreted the high premium as "unreasonable" relative to the simple 3-year average.
2.  **Stuck Watermark / Pagination Failure:** The `update_recent_deals` task was failing to find new deals and prematurely exiting. Investigation revealed that the `keepa_query.json` configuration file contained string values for integer parameters (specifically `dateRange: "4"`), which caused the Keepa API to default to "All Time" searches or behave unpredictably. This caused the system to fetch old data and immediately stop pagination, believing it had "caught up" to the watermark when it hadn't.

## Resolution

### 1. AI Reasonableness Check Fix
*   **File:** `keepa_deals/stable_calculations.py`
*   **Action:** Updated the `_query_xai_for_reasonableness` prompt to explicitly instruct the AI that seasonal items (especially Textbooks) can validly have peak prices **200-400% higher** than the 3-year average.
*   **Context:** Injected the `{season}` variable into the query to ground the AI's assessment (e.g., "Is $150 reasonable *during Jan*?").
*   **Regression Prevention:** Added a mandatory comment in the code explaining this logic to ensure future developers/agents do not remove this critical context.

### 2. Deal Fetching & Watermark Fix
*   **File:** `keepa_query.json`
*   **Action:** Changed `dateRange` from a string `"4"` to an integer `4`. This setting corresponds to Keepa's "All combined" limit drop interval, which the user confirmed provides the desired deal volume (~1200 deals vs ~900 for 90 days).
*   **File:** `keepa_deals/keepa_api.py`
*   **Action:** Added explicit type casting (`int()`) for `page` and `sortType` parameters in `fetch_deals_for_deals` to defend against string injection from configuration files.
*   **Action:** Added a versioned log message `(v_fix_sort)` to confirm the fix is deployed and running.

## Verification
*   **AI Fix:** Verified using a script (`verify_codebase_fix.py`) that imported the actual application code. Confirmed that a known high-seasonality test case ("Calculus: Early Transcendentals", Peak $150, Avg $45) is now **accepted** by the AI, while absurd inputs (Peak $1500) are still **rejected**.
*   **Fetching Fix:** Verified that `keepa_query.json` now contains valid JSON types, aligning with the API's requirements.

## Technical Notes / Learnings
*   **Prompt Context is King:** When using LLMs for numerical validation, simple statistics (like averages) are insufficient for volatile/seasonal data. You must provide the model with the *domain logic* (e.g., "seasonal spikes are normal") for it to judge correctly.
*   **Strict Typing for APIs:** The Keepa API is sensitive to parameter types. Passing `"4"` (string) instead of `4` (int) for `dateRange` or `sortType` can silently fail or revert to defaults, leading to subtle logic bugs like stuck watermarks. Always enforce integer types for these parameters in the Python layer.
