# Dev Log: Financial Model Documentation Alignment
**Date:** 2026-05-28

## Task Overview
The goal of this task was to align four specific documentation files with a newly locked project-wide financial model regarding costs, fees, and profits. The documents needed to strictly reflect the following models:
1. `buy_cost` / `buy_cost_paid` = book price + actual shipping + actual tax. It excludes prep, FBA, and referral fees.
2. `all-in cost` = `buy_cost_paid` + prep fee.
3. Amazon fees (FBA + referral) are strictly subtracted from the price side (list price or sale price) to calculate profit, margin, and ROI.
4. Profit/ROI/Margin are estimates until the actual sale occurs.

The four documents to reconcile were:
1. `Documentation/INFERRED_PRICE_LOGIC.md`
2. `Documentation/Data_Logic.md`
3. `Documentation/Business_Documents/Feature_Tracking.md`
4. `Documentation/System_State.md`

## Challenges Faced
- **Preserving Original Voice:** The core challenge was implementing surgical updates without rewriting or restructuring the existing text. The directive explicitly stated "read-and-reconcile, not rewrite," requiring careful patching.
- **Ambiguity vs. Contradiction:** Determining whether existing text simply used older terminology (like "purchase cost" vs `buy_cost_paid`) or genuinely contradicted the model required careful parsing of the surrounding context.
- **Strict File Scope:** It was imperative to only touch the four specified files and strictly avoid changing anything unrelated to the financial lifecycle.
- **File Length & Reading:** Had to navigate the files strategically using `grep` and `sed` to find the exact wording and lines to update without reading the entire large markdown files, to preserve token limits.

## Solutions Implemented
- **Exploration:** Used `grep -iE 'cost|fee|profit|ROI|margin'` to locate relevant passages in the four files, followed by `sed -n` to extract the full context for each match.
- **Review of `INFERRED_PRICE_LOGIC.md`:** Found no explicit contradictions. The document focuses on price calculation ("List at", "1yr Avg") and briefly mentions profit, but does not define out-of-pocket costs or Amazon fee deductions. Left this file untouched and flagged this finding.
- **Updates to `Data_Logic.md`:** 
  - Redefined "Inputs" in the Business Math section to use `buy_cost_paid`.
  - Replaced the `All-in Cost` formula to explicitly state `buy_cost_paid + Prep Fee`.
  - Clarified that `Profit` is an estimate (`List at - All-in Cost - Total AMZ fees`) until actual sale.
  - Aligned inline cost logic references to use `buy_cost_paid`.
- **Updates to `Feature_Tracking.md`:**
  - Updated "Buy Cost" column references to explicitly use `buy_cost_paid`, noting it excludes Prep Fee and Amazon fees.
  - Clarified that realized profit is calculated using the `all-in cost` against the sale price minus actual FBA/referral fees.
- **Updates to `System_State.md`:**
  - Replaced references of `buy_cost` with `buy_cost_paid` in the Tracking API Architecture section.
  - Clarified the "Dynamic ROI Calculation" section to explicitly state that `All-in Cost` equals `buy_cost_paid + prep fee`.

## Success Status
**Successful**. All relevant documents were successfully updated to reflect the canonical locked financial model while preserving their original structure and tone. The test suite passed successfully following the documentation edits.
