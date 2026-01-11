# Fix Profit Calculation & Restore Backfill Limiter

**Date:** 2026-01-11
**Status:** Successful
**Task Type:** Bug Fix, Feature Restoration, Documentation

## Overview
This task addressed three distinct issues resulting from a sequence of unstable previous development sessions. The primary goals were to fix a logic error preventing profit calculations, restore the "Artificial Backfill Limiter" feature that appeared to be missing due to a git synchronization issue ("forgotten push"), and resolve a UI styling glitch introduced during the restoration.

## 1. Profit Calculation Fix
**Issue:** The "Recalculate" feature (and the dashboard) was showing empty or zero values for Profit and Margin.
**Diagnosis:** The `keepa_deals/recalculator.py` script was fetching data from the database using a mapping where `"Best Price"` was aliased to `"Best_Price"`. However, the internal business logic functions (imported from `business_calculations.py`) expected the current price to be available under the key `"Now"`. Because `"Now"` was missing/None, the profit calculation logic failed silently or returned default values.
**Solution:** Updated the `required_columns_map` in `recalculator.py` to map the database column `"Best Price"` specifically to the key `"Now"`.
```python
# keepa_deals/recalculator.py
required_columns_map = {
    # ...
    "Best Price": "Now", # Changed from "Best_Price"
    # ...
}
```

## 2. Artificial Backfill Limiter Restoration
**Issue:** The user reported that a previously implemented feature, the "Artificial Backfill Limiter" (which stops the backfill task after a certain number of deals), was missing because the changes were never pushed to the repository due to environmental instability.
**Investigation:** Upon inspecting the fresh sandbox environment, it was discovered that the *backend logic* for the limiter (in `keepa_deals/backfiller.py` and `keepa_deals/db_utils.py`) was actually present on the disk, likely carried over or pre-existing in the base image, but the frontend UI and handler logic were missing.
**Challenge:** The challenge was to ensure that this existing backend code was explicitly synchronized with the git repository to resolve the "forgotten push" state.
**Solution:**
*   **Backend:** Implemented the settings handler in `wsgi_handler.py` to save `backfill_limit_enabled` and `backfill_limit_count` to the `system_state` table.
*   **UI:** Added the configuration form to `templates/deals.html`.
*   **Sync:** Forced `keepa_deals/backfiller.py` and `keepa_deals/db_utils.py` to be included in the commit by appending a trivial comment (`# Refreshed`). This guarantees the remote repository matches the functional state of the sandbox.

## 3. UI Visual Fix
**Issue:** After implementing the Backfill Limiter UI, the "Update Limit" button appeared to "leak" or merge with the left yellow border of the card.
**Diagnosis:** The `.settings-card` div had a `border-left` style but lacked sufficient padding or a distinct background color in the global CSS, causing the content to bleed into the border area visually.
**Solution:** Added a specific `<style>` block in `templates/deals.html` to define `.settings-card` with:
*   `padding: 25px;` (to separate content from borders)
*   `background-color: rgba(0, 0, 0, 0.2);` (to provide visual containment)
*   `border-radius: 8px;`

## Verification
*   **Profit:** Verified via code analysis that the mapping now aligns with the `calculate_all_in_cost` requirements.
*   **Limiter UI:** Verified via Playwright script (`verify_limiter_ui.py`) and screenshot inspection that the UI is present, properly styled, and the button does not overlap the border.
*   **Limiter Logic:** Verified via code inspection that `backfiller.py` contains the check: `if get_system_state('backfill_limit_enabled') == 'true': ...`.

## Key Files Changed
*   `keepa_deals/recalculator.py`
*   `keepa_deals/backfiller.py`
*   `keepa_deals/db_utils.py`
*   `wsgi_handler.py`
*   `templates/deals.html`
