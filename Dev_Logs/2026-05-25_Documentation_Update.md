# Dev Log: Documentation Update

**Date:** 2026-05-25
**Author:** Jules (AI Agent)
**Status:** Success

## Overview
The goal of this task was to update the documentation files to accurately reflect the current state of the codebase. I reviewed recent dev logs to identify drift in the documentation and made the necessary structural and content updates.

## Files Read
- `README.md`
- `AGENTS.md`
- `Documentation/System_Architecture.md`
- `Documentation/Feature_Deals_Dashboard.md`
- `Documentation/Data_Logic.md`
- `Documentation/Dashboard_Specification.md`
- `Documentation/System_State.md`
- `Documentation/INFERRED_PRICE_LOGIC.md`
- `Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`
- `Documentation/Token_Management_Strategy.md`
- `Documentation/Capacity_Planning.md`
- `Dev_Logs/2026-05-24_Add_ASIN_To_Active_Inventory.md`
- `Dev_Logs/2026-05-24_Editable_Buy_Cost_Potential_Buys.md`
- `Dev_Logs/2026-05-23_Diagnose_Sales_Profit_Tab.md`
- `Dev_Logs/2026-05-23_Remove_Fees_Column_From_Sales_Profit_Tab.md`
- `Dev_Logs/2026-05-14_Documentation_Updates_for_Mentor_and_Architecture.md`
- `Dev_Logs/2026-05-12_Fix_WSGI_Hangs.md`
- `Dev_Logs/2026-05-12_Pass_1_and_2_Seasonal_and_Trend_Refinements.md`
- `Dev_Logs/2026-05-13_Add_Pass2_Strategic_Corrections.md`

## Files Modified

- **`Documentation/System_State.md`:** 
  - Documented that the `inventory_ledger` has an `asin` column now (from "Add ASIN To Active Inventory" dev log).
  - Documented the removal of the Fees column from the Sales & Profit tab because the SP-API Orders v0 endpoint doesn't return fees (from "Remove Fees Column" dev log). Realized profit is estimated dynamically on the backend.
  - Documented the `buy_cost_confirmed` boolean flag in `inventory_ledger` and the editable `buy_cost` capability for "Potential Buys" (from "Editable Buy Cost" dev log).

- **`Documentation/System_Architecture.md`:** 
  - Documented the WSGI Hangs issue caused by C-extension deadlocks within isolated `mod_wsgi` sub-interpreters and explicitly recommended using the `WSGIApplicationGroup %{GLOBAL}` directive (from "Fix WSGI Hangs" dev log).
  - Updated the Prime Picks (Agent's Choice Evaluator) pass 1 mechanism to explicitly detail the 365-day average for safe offer-trend deduplication and the Year-Round Velocity Cap (Rank > 2,000,000) (from "Pass 1 and 2 Seasonal and Trend Refinements" dev log).
  - Added a note that Prime Picks caching is skipped gracefully if Pass 2 (xAI) fails to preserve the last known valid run.

- **`Documentation/Data_Logic.md`:** 
  - Updated the "Business & Financial Metrics" section to include the inline editable `buy_cost` logic for Tracking/Potential Buys, ensuring exact out-of-pocket metrics are recorded.
  - Added documentation about the "Realized Profit (Sales History)" estimation strategy due to the removal of the Fees column based on SP-API limitations.

- **`README.md`:**
  - Bumped the Last Updated timestamp to May 25, 2026.

## Files Reviewed But Intentionally Not Modified
- **`Documentation/Dashboard_Specification.md`:** The column breakdowns and filters remain the same, as recent work mainly impacted Tracking rather than Dashboard Deals UI.
- **`Documentation/INFERRED_PRICE_LOGIC.md`:** The pricing core logic was untouched during recent Tracking and Prime Picks tuning.
- **`Documentation/Token_Management_Strategy.md`:** No recent changes were made to how Keepa tokens or XAI quotas are managed.
- **`Documentation/Capacity_Planning.md`:** Performance baseline metrics and capacity goals remain unchanged.
- **`Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`:** The admin features for guided learning didn't change.
- **`AGENTS.md`:** Retained all current strict rules and architectural instructions without changes since no operational guidelines shifted.
- **`Documentation/Feature_Deals_Dashboard.md`:** Functionality of the dashboard hasn't been impacted by the recent tracking-specific features.
