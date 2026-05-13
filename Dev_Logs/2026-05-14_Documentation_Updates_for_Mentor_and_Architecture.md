# Dev Log: Documentation Updates for Mentor and Architecture

**Date:** 2026-05-14
**Status:** Successful

## Task Overview
The goal of this task was to identify documentation drift across the full documentation set and update it to accurately reflect recent codebase changes. The primary focus was on recent enhancements to the AI Mentor pipeline (Advice from Ava and Mentor Chat) regarding strategic alignment, as well as confirming other recent fixes (like WSGI hangs and Prime Picks filtering) were documented.

## Challenges Faced
- Determining exactly which documentation files needed updates, as changes to core logic (like `STRATEGIC_CORRECTIONS`) impact both high-level system architecture and user-facing feature descriptions.
- Ensuring the new `dual-strategy` framework (high-velocity flips vs. seasonal holds) was accurately described across multiple areas without duplicating large blocks of text.

## Actions Taken
### Files Read
- `README.md`
- `AGENTS.md`
- `Documentation/System_Architecture.md`
- `Documentation/Data_Logic.md`
- `Documentation/Feature_Deals_Dashboard.md`
- `Documentation/Dashboard_Specification.md`
- `Documentation/INFERRED_PRICE_LOGIC.md`
- `Documentation/Capacity_Planning.md`
- `Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`
- `Documentation/Token_Management_Strategy.md`
- `Documentation/System_State.md`
- `Dev_Logs/2026-05-11_Centralize_SQLite_Connection_And_Fix_Leaks.md`
- `Dev_Logs/2026-05-12_Fix_WSGI_Hangs.md`
- `Dev_Logs/2026-05-12_Pass_1_and_2_Seasonal_and_Trend_Refinements.md`
- `Dev_Logs/2026-05-13_Add_Dual_Strategy_Framing_to_Mentor.md`
- `Dev_Logs/2026-05-13_Add_Pass2_Strategic_Corrections.md`

### Files Modified
- **`Documentation/System_Architecture.md`:** Updated the 'Advice from Ava' and 'Mentor Chat' sections to note that they now share a common `STRATEGIC_CORRECTIONS` block injected from `keepa_deals/ava_advisor.py`, ensuring consistent evaluation logic, including dual-strategy framing.
- **`Documentation/Feature_Deals_Dashboard.md`:** Updated the 'My Mentor (AI Overlay)' and 'Mentor Chat Integration' sections to mention that they evaluate candidates using the new dual-strategy framework to prevent bias toward high-velocity replens.
- **`AGENTS.md`:** Appended a new entry under "Recent Fixes" detailing the extraction of `STRATEGIC_CORRECTIONS` into a shared constant and the addition of Dual Strategy Framing for Mentor Chat and Advice from Ava.
- **`README.md`:** Bumped the "Last Updated" timestamp to May 14, 2026, and updated the version notes.

### Files Intentionally Reviewed but Unmodified
- **`Documentation/Data_Logic.md`:** Verified that the "Offers Trend" section correctly lists the 365-day average used for Pass 1 deduplication.
- **`Documentation/INFERRED_PRICE_LOGIC.md`:** No recent changes impacted the inferred pricing core logic described here.
- **`Documentation/Dashboard_Specification.md`:** Filter labels and column specifications remain unchanged.
- **`Documentation/System_State.md`:** No state-tracking architectural changes were made recently.

## Conclusion
The documentation has been successfully brought up to date with the latest architectural shifts, particularly the consolidation of AI strategy logic in the mentor pipeline.