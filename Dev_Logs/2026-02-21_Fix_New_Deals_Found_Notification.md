# Fix "New Deals Found" Notification Logic

## Overview
The "New Deals Found" notification in the Deals Dashboard was missing. Investigation revealed a logic flaw in how the baseline deal count was initialized, preventing the notification from appearing even when new deals were available.

## Challenges Faced
- **Logic Mismatch:** The dashboard initialized the local baseline count (`currentTotalRecords`) using `total_db_records` (the raw count of all rows in the `deals` database). However, the polling mechanism (`/api/deal-count`) returns a count that respects active filters (including default filters like "Profit > 0").
- **Consequence:** Since `total_db_records` (unfiltered) is almost always greater than `filtered_count`, the difference (`serverCount - currentTotalRecords`) was persistently negative, causing the notification to remain hidden.
- **Verification Complexity:** Verifying the fix required simulating a state where the filtered count increases relative to the baseline, which is difficult without live data ingestion. A reproduction script (`reproduce_issue.py`) was used to mathematically prove the flaw and the fix.

## Resolution
- **Frontend Fix:** Modified `templates/dashboard.html` to initialize `currentTotalRecords` using `data.pagination.total_records` (the filtered count returned by the initial API call) instead of `total_db_records`.
- **Robustness:** Added a check for `typeof ... !== 'undefined'` to ensure the baseline is correctly updated even when the returned count is validly `0`.
- **Outcome:** The notification now correctly compares "Filtered Baseline" vs "Filtered Current", showing the "X New Deals found" message whenever new matching deals arrive.

## Verification
- **Logic Test:** A Python script confirmed that the old logic produced negative differences (failure) while the new logic produced positive differences (success) when new deals were added.
- **Visual Test:** A Playwright script (`verify_dashboard.py`) successfully logged in, injected a mock state (simulating a new deal arrival), and captured a screenshot confirming the notification is visible and correctly styled.
