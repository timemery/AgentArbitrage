## Dev Log: Add Profit, ROI, and Margin to Potential Buys Tab (Partial Implementation)

### Overview

Added the structure and frontend support for Profit ($), ROI (%), and Margin (%) columns to the "Potential Buys" tab on the Tracking page. The columns are visible, but the calculation logic populating them was found to be more complex than anticipated and remains incomplete. Currently, values display as em dashes (`—`). The calculation logic will be addressed in a subsequent task.

### Implementation Details

1. Frontend Modification:
   - Modified `renderPotential()` in `templates/tracking.html` to display the new columns (Profit, ROI, Margin).
   - Added column headers in the correct order: Title, ASIN, Est. Cost, Date, **Profit, ROI, Margin**, Actions.
   - Formatted values correctly (currency `$` for Profit, `%` for ROI and Margin), handling missing values with an em dash (`—`).
   - Adjusted the empty/spacer row `colspan` to `8`.
   - Verified changes via Playwright automation.

### Investigation Findings for Next Task

During investigation, the following data flow for Dashboard metric calculations was definitively traced:

- **Pre-formatted Strings:** The `deals` table stores `Profit`, `Margin`, and `All_in_Cost` as pre-formatted strings (e.g., `$12.34`, `30.5%`). The Dashboard (`api_deals` in `wsgi_handler.py`) fetches these strings directly and sends them to the UI.
- **Dynamic ROI:** The Dashboard UI calculates `ROI` dynamically on the fly within `templates/dashboard.html` using the formula `(deal.Profit / deal.All_in_Cost) * 100` before rendering. The backend filtering logic handles this dynamically as well using SQL `CAST`.
- **Computation Source:** The formatted strings are computed and stored during the ingestion phase. This logic resides in `_process_single_deal` within `keepa_deals/processing.py`. It calls `calculate_profit_and_margin` and updates the `row_data` dictionary before saving it to the database.
- **Raw Inputs:** The raw input columns required for these calculations (`List_at`, `FBA_PickandPack_Fee`, `Referral_Fee_Percent`, `Shipping_Included`) *do* exist as actual float/text values in the `deals` table.

Next task scope: replicate the raw-input calculation path from `processing.py` so the Tracking page can produce numeric values that match Dashboard output. Additionally, the next task will introduce user-editable Buy Cost on Potential Buys with on-the-fly recalculation — required because Dashboard estimates rarely match actual Amazon prices, and Potential Buys is the user's only decision-point window before purchase.

### Product Context

This task was halted during implementation because review identified that the displayed Profit/ROI/Margin would be based on Dashboard estimates, which rarely match the actual Amazon prices users see when clicking through. With no edit capability until inventory reaches the warehouse (1-2 months later), this would produce misleading data at the user's primary decision point. The next task addresses both the calculation and the edit capability.

### Status

- Frontend table structure committed to repo; pending deployment by Tim.
- Calculation logic intentionally deferred to next task.
- No backend changes were deployed.
