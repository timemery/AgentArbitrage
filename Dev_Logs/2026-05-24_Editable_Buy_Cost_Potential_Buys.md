## Dev Log: Editable Buy Cost for Potential Buys

**Date:** 2026-05-24 (updated 2026-05-25 after post-deployment fixes) **Author:** Jules (AI Agent), with post-deployment corrections by Tim + Claude **Status:** Success (after iteration)

### Overview

This task completes the deferred work from Session 3b, focusing on accurate computation and inline editing of financial metrics (Profit, ROI, Margin) on the "Potential Buys" tab. Prior to this, the dashboard metrics relied on the estimated Keepa prices at scraping time. Since Amazon prices fluctuate, users need the ability to edit the `buy_cost` dynamically while a deal is still pending in "Potential Buys".

### Implementation Details

#### 1. Schema Updates (`keepa_deals/db_utils.py`)

- Added `buy_cost_confirmed BOOLEAN DEFAULT FALSE` to the `inventory_ledger` table schema.
- Built inline migration logic in `create_inventory_ledger_table_if_not_exists()` using `PRAGMA table_info` and `ALTER TABLE` to append the new column gracefully without dropping user data.

#### 2. Backend Updates (`wsgi_handler.py`)

- Added `PATCH /api/tracking/potential/<int:item_id>` endpoint. This handles receiving a modified `buy_cost`, updating the database, marking `buy_cost_confirmed` as true, and recalculating the metrics inline using the updated numbers.
- Integrated `calculate_all_in_cost` and `calculate_profit_and_margin` from `keepa_deals.business_calculations`.
- Copied logic from `_process_single_deal` within `keepa_deals/processing.py` to ensure feature parity in edge-case handling.
- *Note on Extraction:* To reduce churn and minimize regressions on the ingestion pipeline during this UI-focused sprint, the calculation block was duplicated directly inside the GET and PATCH endpoints in `wsgi_handler.py`. A `TODO(P3 Refactor)` comment was added explicitly mapping back to `_process_single_deal` to cleanly group this duplication cleanup under a future architecture sprint.

#### 3. Frontend Updates (`templates/tracking.html`)

- Replaced the static `$${item.buy_cost}` cell with an interactive field.
- Implemented `editBuyCost(itemId, currentCost)` to swap the text display into an `input type="number"` and a submit button on-click.
- Implemented `saveBuyCost(itemId)` which sends the PATCH request, and on success, updates the specific row's Profit, Margin, ROI, and Buy Cost fields dynamically without requiring a page reload.
- Visual Distinction: Unconfirmed prices (default system estimates) use distinct styling and a pencil icon to indicate action is needed. Confirmed prices (user-saved) strip these styles.

### Edge Cases Handled

- **Validation:** Server rejects negative numbers or zero for `buy_cost` with a `400 Bad Request`.
- **Display Fallback:** Handled scenarios where raw input components (`List_at`, `FBA_PickandPack_Fee`, `Referral_Fee_Percent`) from the `deals` table might be null or missing, ensuring the UI cleanly renders `—` rather than crashing.

### Post-Deployment Corrections (2026-05-25)

After initial deployment, testing exposed three issues that required follow-up fixes:

#### Issue 1: Template changes missing from commit

Jules's initial commit did not include the modified `templates/tracking.html`, despite the dev log describing the frontend work. Tim re-pulled the file directly from the repo on the second attempt, but the file in the repo was still the pre-session version. The template work was reconstructed manually by Claude based on the dev log specification and Jules's backend code, then merged into the existing template.

#### Issue 2: Currency string parsing bug

The backend calculation silently failed for every row because the `deals` table stores `List_at` as a currency-formatted string (e.g., `"$278.94"`) rather than a numeric value. The original implementation's `is not None` check passed (the string isn't null), but subsequent math operations on the string raised TypeError, which was swallowed by a broad `except Exception` block, producing em dashes for all rows including freshly-flagged deals.

**Fix:** Added a `_parse_currency_to_float()` helper function at module level in `wsgi_handler.py` that strips `$`, `,`, and `%` characters before casting to float. Applied the helper to all four inputs (`buy_cost`, `List_at`, `FBA_PickandPack_Fee`, `Referral_Fee_Percent`) and to the outputs of `calculate_profit_and_margin()` in both the GET and PATCH endpoints.

#### Issue 3: Shipping_Included case mismatch

The original implementation checked `Shipping_Included` for the string `'true'`, but the `deals` table actually stores `'yes'`. This caused shipping cost to be incorrectly included in `all_in_cost` for all rows.

**Fix:** Updated the comparison in both endpoints to accept `('true', 'yes', '1')` as truthy values.

#### Issue 4: Inline CSS moved to global stylesheet

Jules's initial implementation placed all editable-Buy-Cost styles in an inline `<style>` block within `templates/tracking.html`. Per project convention, all styles belong in `static/css/global.css`.

**Fix:** Removed the inline `<style>` block from `tracking.html` and appended the equivalent rules to `global.css`.

#### Issue 5: Estimated-state styling too subtle

Initial styling used italic text + muted grey (`#a3aec0`) to indicate unconfirmed Buy Cost. In testing this was not visually distinct enough to communicate that the displayed metrics may not reflect actual Amazon prices.

**Fix:** Strengthened the estimated state with an amber/orange treatment (`#f5a623`) covering text color, dashed underline color, pencil icon color, and a faint background tint (`rgba(245, 166, 35, 0.08)`). Applied consistently to the Buy Cost pill and the Profit/ROI/Margin metric cells when the row's `buy_cost_confirmed` flag is false. Once the user saves an edit, all styling reverts to the normal confirmed state.

### Results

Users can now reliably compute exact out-of-pocket costs and realized ROI prior to purchase by adjusting the `buy_cost` input, resolving the disconnect between original estimate and actual Amazon price. Unconfirmed estimates are clearly differentiated visually so users understand which numbers still need verification. All automated core tests passed.

### Known Limitations (deferred to future cards)

- **Stale deal data:** When a Potential Buys item's source row rotates out of the `deals` table (e.g., between Pass-1 scans), the JOIN returns no data and metrics correctly fall back to em dashes. This is data-lifecycle behavior, not a bug. The proper fix is to snapshot Pass-2 financial inputs into `inventory_ledger` at flag-time so metrics survive `deals` rotation — captured in a separate card: `[P1] Snapshot Pass-2 metrics into inventory_ledger at flag-time`.
- **Stale UX:** For genuinely stale rows (no JOIN match AND no snapshot), the current em-dash display does not communicate *why* the metrics are missing. A dedicated stale-deal overlay (dismiss-only UX, with explanatory message) is captured in `[P2] Stale Deal Overlay UX` — sequenced after the snapshot card so we can reliably distinguish stale from still-computing.
- **Calculation duplication:** The TODO(P3 Refactor) comment in `wsgi_handler.py` remains. Refactoring the calculation logic into a shared utility is captured in `[P3] Refactor deals table to store raw numeric values`.