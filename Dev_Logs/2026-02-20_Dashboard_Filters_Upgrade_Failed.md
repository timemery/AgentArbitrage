# Dashboard Filters Upgrade (Failed)

## Overview
The goal of this task was to upgrade the Dashboard Filters in `dashboard.html` and `wsgi_handler.py`.
The specific requirements were:
1.  **Replace "Min. Margin" with "Min. ROI".**
2.  **Add "Min. Drops (30d)" filter.**
3.  **Implement "Exclude Conditions" checkboxes** (replacing the previous "Include" logic).
4.  **Add an "Optimal Suggested Filters" checkbox** (Magic Button) that presets sliders to specific values ($4 Profit, 35% ROI, 1 Drop, etc.).
5.  **Persist filter settings** using `localStorage`.

## Actions Taken
*   **Backend (`wsgi_handler.py`):**
    *   Updated `api_deals` to accept `roi_gte`, `drops_30_gte`, and `excluded_conditions` parameters.
    *   Refactored the SQL query to remove the `AS d` alias and use the explicit table name `deals` to prevent "no such column" errors (a common SQLite issue when mixing aliases in WHERE/ORDER BY clauses).
    *   Added `create_deals_table_if_not_exists()` to the startup sequence to ensure the `deals` table has the necessary columns (`Sales_Rank_Drops_last_30_days`).
*   **Frontend (`dashboard.html`):**
    *   Overhauled the Filter Panel UI to match the "Full Panel" design.
    *   Implemented the "Optimal Filters" logic in JavaScript, which sets slider values and unchecks exclusion boxes.
    *   Implemented `localStorage` saving/loading for all filter inputs.
    *   Updated the `fetchDeals` function to pass the new parameters to the API.

## Challenges & Failure
*   **Persistent "Error loading deals":** Despite refactoring the SQL query to remove aliases (which fixed a similar issue in `deal_count`), the `api_deals` endpoint continued to fail in the user's environment with "Error loading deals. Please try again later."
*   **Environment/Git Sync Issues:** The user reported being unable to see the committed branches (`dashboard-query-fix-alias`, `fix-dashboard-filters-crash`). This suggests a disconnect between the sandbox environment's git state and the user's remote repository, preventing the fixes from actually being deployed or verified by the user.
*   **Database Schema:** There was a concern that the `Sales_Rank_Drops_last_30_days` column might be missing from the user's existing `deals.db`, causing the query to fail despite the code being correct. The `create_deals_table_if_not_exists()` addition was intended to solve this but could not be verified due to the deployment failure.

## Conclusion
The code logic appears correct locally and passes verification scripts (returning 2 deals with correct filtering). However, the task is considered **failed** because the user cannot access the working state due to environment/deployment issues, and the error persists in their view.

## Next Steps for Future Agent
*   **Investigate Git Connectivity:** Verify why branches pushed from the sandbox are not visible to the user.
*   **Debug `api_deals` Live:** Use `print()` debugging or detailed logging in `wsgi_handler.py` to capture the *exact* SQL error message causing the 500 response in the user's environment. The generic "Error loading deals" message hides the root cause (e.g., is it `no such column`, `ambiguous column`, or a logic error?).
*   **Verify DB Schema:** Ensure the user's `deals.db` actually has the `Sales_Rank_Drops_last_30_days` column.
