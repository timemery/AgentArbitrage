## Dev Log: Snapshot Pass-2 Financial Metrics into inventory_ledger at Flag-Time

**Date:** 2026-05-29 **Task:** Snapshot Pass-2 financial metrics into `inventory_ledger` at flag-time.

### Overview

The goal of this task was to implement a mechanism to capture and persist the exact financial metric inputs that drive the display on the Dashboard's Potential Buys overlay at the precise moment a user flags a deal (clicks "Buy"). This solves an issue where the matching Potential Buys row drops to displaying em-dashes for Profit, Margin, and ROI if the underlying `deals` database row is refreshed or dropped by a subsequent Pass-2 pipeline run.

This was the first card in a three-card sequence culminating in a new Confirmed Buys tab, taking inputs at flag-time to serve as resilient fallbacks for tracking UI functionality.

### Challenges

- **Drift Risk (pre-flag, during in-flight recalc):** The Dashboard relies on global `settings.json` parameters (Prep Fee, Estimated Tax, and Estimated Shipping) and the `deals` table for displayed Profit/Margin/ROI. When a user changes Settings, the background recalculator updates the `deals` table asynchronously — there's a window between the Settings save and the recalc completion during which the Dashboard displays old Profit values while `business_load_settings()` returns new values. A user clicking Buy during that window would snapshot fresh Settings values that disagree with the still-stale displayed values. In practice this window is small and the case is rare (Tim's prep fee has not changed in 3 years), but the architectural concern is captured in the follow-up card `[P2][Investigate] Dashboard Profit drift after Settings change`.
- **State Fallback Execution:** The data needed for calculating accurate display values for tracked inventory must seamlessly shift from `deals` to the `inventory_ledger` snapshot variables only when the original record vanishes, meaning we needed robust `NULL` fallbacks.

### Solutions

1. **Schema Migration:** Created and executed a DB migration script (`Migrations/add_inventory_ledger_snapshots.py`) using the existing `get_db_connection()` framework to add seven nullable snapshot columns to the `inventory_ledger` table (`snapshot_list_at`, `snapshot_fba_fee`, `snapshot_referral_pct`, `snapshot_shipping_included`, `snapshot_estimated_tax`, `snapshot_estimated_shipping`, `snapshot_prep_fee`).

2. **Snapshot Write Path Modification:** Modified the `/api/inventory/potential` POST endpoint (`add_potential_buy` in `wsgi_handler.py`) to query the exact `List_at`, `FBA_PickandPack_Fee`, `Referral_Fee_Percent`, and `Shipping_Included` values from the `deals` DB and retrieve active configuration inputs using `business_load_settings()`. These variables are injected directly into the `inventory_ledger` row creation.

3. Display Fallbacks:

    Updated the display calculations in 

   ```
   wsgi_handler.py
   ```

    (

   ```
   get_potential_inventory
   ```

    and 

   ```
   update_potential_buy_cost
   ```

   ). To preserve exact Dashboard views if the 

   ```
   deals
   ```

    DB row rotates out:

   - Replaced `deal.*` missing metrics dynamically with `snapshot_*` counterparts.
   - If the deals list is absent, created a cloned config map injecting `snapshot_estimated_tax`, `snapshot_estimated_shipping`, and `snapshot_prep_fee` directly into the `calculate_all_in_cost` logic for accurate Profit/Margin/ROI estimates.

### Outcome

The task was successfully completed. Live production smoke test verified:

- Migration ran cleanly with all seven nullable REAL columns present on `inventory_ledger`.
- Flag-time snapshot write: flagged ASIN `842703041X` populated all seven snapshot fields on `inventory_ledger` row 219 (`snapshot_list_at=120.56, snapshot_fba_fee=5.88, snapshot_referral_pct=15.0, snapshot_shipping_included=0.0, snapshot_estimated_tax=5.00, snapshot_estimated_shipping=3.99, snapshot_prep_fee=2.75`). Potential Buys display matched the Dashboard.
- Display fallback: manually deleted the ASIN's `deals` row and confirmed Potential Buys continued to display the same Profit/Margin/ROI values, now sourced from snapshots.
- Edit-time recalc on a snapshot-only row (no `deals` row present) correctly used snapshot tax/shipping/prep_fee values.
- Pre-migration Potential Buys rows (e.g., ASIN `194665700X` from May 25) correctly show em-dash, as expected — they have no snapshots to fall back to, and no backfill was planned per the spec.

The codebase is now prepared to utilize these snapshots for building the Confirmed Buys sequence.

### Known follow-ups

Two follow-up cards spawned from this work, both `[P2][Investigate]`:

- **ROI formula verification** — during testing, the displayed ROI numbers could not be reconciled to the simple `Profit / (buy_cost + prep_fee)` formula documented in `Data_Logic.md`, nor to obvious variants including tax/shipping in the all-in cost. Pre-existing condition unrelated to this card; needs a separate audit.
- **Dashboard Profit drift after Settings change** — see Challenges section above. The async recalc window allows displayed values to drift from current Settings until Pass-2 catches up. Snapshot work captures whatever is displayed (faithful drift), so this is a downstream symptom of a pre-existing Dashboard behavior, not something Card 1 introduced.
