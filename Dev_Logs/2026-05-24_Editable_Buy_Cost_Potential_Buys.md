# Dev Log: Editable Buy Cost for Potential Buys

**Date:** 2026-05-24
**Author:** Jules (AI Agent)
**Status:** Success

## Overview
This task completes the deferred work from Session 3b, focusing on accurate computation and inline editing of financial metrics (Profit, ROI, Margin) on the "Potential Buys" tab. Prior to this, the dashboard metrics relied on the estimated Keepa prices at scraping time. Since Amazon prices fluctuate, users need the ability to edit the `buy_cost` dynamically while a deal is still pending in "Potential Buys".

## Implementation Details

### 1. Schema Updates (`keepa_deals/db_utils.py`)
- Added `buy_cost_confirmed BOOLEAN DEFAULT FALSE` to the `inventory_ledger` table schema.
- Built inline migration logic in `create_inventory_ledger_table_if_not_exists()` using `PRAGMA table_info` and `ALTER TABLE` to append the new column gracefully without dropping user data.

### 2. Backend Updates (`wsgi_handler.py`)
- Added `PATCH /api/tracking/potential/<int:item_id>` endpoint. This handles receiving a modified `buy_cost`, updating the database, marking `buy_cost_confirmed` as true, and recalculating the metrics inline using the updated numbers.
- Integrated `calculate_all_in_cost` and `calculate_profit_and_margin` from `keepa_deals.business_calculations`.
- Copied logic from `_process_single_deal` within `keepa_deals/processing.py` to ensure feature parity in edge-case handling.
- *Note on Extraction:* To reduce churn and minimize regressions on the ingestion pipeline during this UI-focused sprint, the calculation block was duplicated directly inside the GET and PATCH endpoints in `wsgi_handler.py`. A `TODO(P3 Refactor)` comment was added explicitly mapping back to `_process_single_deal` to cleanly group this duplication cleanup under a future architecture sprint.

### 3. Frontend Updates (`templates/tracking.html`)
- Replaced the static `$${item.buy_cost}` cell with an interactive field.
- Implemented `editBuyCost(itemId, currentCost)` to swap the text display into an `input type="number"` and a submit button on-click.
- Implemented `saveBuyCost(itemId)` which sends the PATCH request, and on success, updates the specific row's Profit, Margin, ROI, and Buy Cost fields dynamically without requiring a page reload.
- Visual Distinction: Unconfirmed prices (default system estimates) use italicized styling, muted colors, and a pencil icon to indicate action is needed. Confirmed prices (user-saved) strip these styles.

## Edge Cases Handled
- **Validation:** Server rejects negative numbers or zero for `buy_cost` with a `400 Bad Request`.
- **Display Fallback:** Handled scenarios where raw input components (`List_at`, `FBA_PickandPack_Fee`, `Referral_Fee_Percent`) from the `deals` table might be null or missing, ensuring the UI cleanly renders `—` rather than crashing.

## Results
Users can now reliably compute exact out-of-pocket costs and realized ROI prior to purchase by adjusting the `buy_cost` input, resolving the disconnect between original estimate and actual Amazon price. All automated core tests passed.