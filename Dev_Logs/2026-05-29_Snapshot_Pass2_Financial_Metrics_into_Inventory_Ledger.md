# Dev Log: Snapshot Pass-2 Financial Metrics into inventory_ledger at Flag-Time

**Date:** 2026-05-29
**Task:** Snapshot Pass-2 financial metrics into `inventory_ledger` at flag-time.

## Overview
The goal of this task was to implement a mechanism to capture and persist the exact financial metric inputs that drive the display on the Dashboard's Potential Buys overlay at the precise moment a user flags a deal (clicks "Buy"). This solves an issue where the matching Potential Buys row drops to displaying em-dashes for Profit, Margin, and ROI if the underlying `deals` database row is refreshed or dropped by a subsequent Pass-2 pipeline run.

This was the first part in a three-card sequence culminating in a new Confirmed Buys tab, taking inputs at flag-time to serve as resilient fallbacks for tracking UI functionality.

## Challenges
* **Drift Risk:** Since the Dashboard relies on global `settings.json` parameters (Prep Fee, Estimated Tax, and Estimated Shipping) and live `deals` row information for displaying accurate financial calculations, any changes to Settings after a flag-click but before a background recalculation could lead to drift between what was originally seen on the Dashboard vs. the snapshotted display values in `inventory_ledger`.
* **State Fallback Execution:** The data needed for calculating accurate display values for tracked inventory must seamlessly shift from `deals` to the `inventory_ledger` snapshot variables only when the original record vanishes, meaning we needed robust `NULL` fallbacks.

## Solutions
1. **Schema Migration:** Created and executed a DB migration script (`Migrations/add_inventory_ledger_snapshots.py`) using the existing `get_db_connection()` framework to add seven nullable snapshot columns to the `inventory_ledger` table (`snapshot_list_at`, `snapshot_fba_fee`, `snapshot_referral_pct`, `snapshot_shipping_included`, `snapshot_estimated_tax`, `snapshot_estimated_shipping`, `snapshot_prep_fee`).
2. **Snapshot Write Path Modification:** Modified the `/api/inventory/potential` POST endpoint (`add_potential_buy` in `wsgi_handler.py`) to query the exact `List_at`, `FBA_PickandPack_Fee`, `Referral_Fee_Percent`, and `Shipping_Included` values from the `deals` DB and retrieve active configuration inputs using `business_load_settings()`. We ensured these variables are injected straight into the `inventory_ledger` row creation.
3. **Display Fallbacks:** Updated the display calculations in `wsgi_handler.py` (`get_potential_inventory` and `update_potential_buy_cost`). To preserve exact Dashboard views if the `deals` DB row rotates out:
   * Replaced `deal.*` missing metrics dynamically with `snapshot_*` counterparts.
   * If the deals list is absent, created a cloned config map injecting `snapshot_estimated_tax`, `snapshot_estimated_shipping`, and `snapshot_prep_fee` directly into the `calculate_all_in_cost` logic for accurate Profit/Margin/ROI estimates.

## Outcome
The task was successfully completed. The migration ran accurately with no missing columns, and tests were fully validated with no functional regressions to the `inventory_ledger` flows. The codebase is now prepared to utilize these snapshots for building the Confirmed Buys sequence.
