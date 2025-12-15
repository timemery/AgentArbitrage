# Next Task: Debug "Spinning Gated Column" & Investigate Rejection Rate

## Context
The previous agent (Jules) implemented condition-aware restriction checks. However, the user reports that the "Gated" column on the dashboard shows a spinning loading indicator indefinitely (2+ hours) for 19 deals. Additionally, a new diagnostic script revealed that 98.5% of fetched deals are being rejected because of "Missing List at" price.

## Primary Objective: Fix the "Spinning Spinner"
The "Spinning" status means the frontend believes a restriction check is pending (value is NULL or specific status), but the background task has not updated it.

### Diagnostic Steps
1.  **Check Database Status:**
    - Run: `sqlite3 deals.db "SELECT is_restricted, approval_url FROM user_restrictions LIMIT 10;"`
    - If empty or NULL, the task is not saving data.
2.  **Check Celery Worker Logs:**
    - **CRITICAL:** Do NOT read the full file. Use: `tail -n 100 celery_worker.log`
    - Look for errors in `check_all_restrictions_for_user`.
    - Look for "conditionType" related errors (e.g., if Amazon rejected a specific mapped condition).
3.  **Verify Token Refresh:**
    - The task attempts to refresh the SP-API token. If this fails, it might exit early. Check logs for "Failed to refresh SP-API token".

### Potential Fixes
- **Error Handling:** Ensure `check_restrictions` catches *all* exceptions inside the loop so one bad ASIN/Condition doesn't kill the batch.
- **Generic Fallback:** If a specific condition check (e.g., `used_very_good`) fails with a 400 error from Amazon, fall back to a generic check (no `conditionType`) automatically.

## Secondary Objective: Investigate High Rejection Rate
- **Insight:** 98.5% of deals are dropped because `List at` is missing.
- **Source:** `keepa_deals/processing.py` excludes deals if `row_data.get('List at')` is missing.
- **Root Cause Analysis:**
    - Investigate `keepa_deals/stable_calculations.py` -> `get_list_at_price`.
    - Is the "Peak Season" calculation failing?
    - Is the AI validation (`_query_xai_for_reasonableness`) rejecting everything?
    - **Action:** Add detailed logging to `get_list_at_price` to see *why* it returns None.

## Tools Available
- `Diagnostics/count_stats.sh`: Run this to see the current rejection stats.
- `Diagnostics/diag_test_sp_api.py`: Use this to test SP-API connectivity in isolation.
