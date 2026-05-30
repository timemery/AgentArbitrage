# Implement Confirmed Buys (Card 2)

## Overview
This task implemented the backend schema, migration, and endpoint changes for the new Confirmed Buys feature as outlined in `Confirmed_Buys_Build_Spec.md`. The goal: separate manually purchased items into their own ledger (`confirmed_buys` and `confirmed_buy_units`) to prevent dual-write collisions with the SP-API's authoritative ownership of `inventory_ledger`.

## Actions Taken

- **Schema Update**: Added `create_confirmed_buys_table_if_not_exists` and `create_confirmed_buy_units_table_if_not_exists` to `keepa_deals/db_utils.py`. The new tables include snapshot fields (list_at, fba_fee, referral_pct, shipping_included, estimated_tax, estimated_shipping, prep_fee) copied at Confirm time from `inventory_ledger`, plus `prep_fee_at_purchase` locked from Settings at the moment of confirmation. `confirmed_buy_units` is keyed to `confirmed_buys` with optional SKU and forward-link columns for future Active Inventory / Sales Ledger reconciliation. Both creation functions were also wired into the WSGI startup block and into `migrate_confirmed_buys.py` so the migration is self-sufficient regardless of whether WSGI has been restarted.

- **Data Migration**: Created `migrate_confirmed_buys.py` to:
  1. Clean up `DISMISSED` tombstone rows (`source = 'Dashboard' AND status = 'DISMISSED'`) that should no longer exist now that Dismiss is a hard DELETE.
  2. Identify manually-confirmed buys (`status = 'PURCHASED' AND source = 'Dashboard'`) and move them to `confirmed_buys`.
  3. Use the current Settings `prep_fee_per_book` as `prep_fee_at_purchase` for backfilled rows, with a hardcoded condition of `'4'` (Used - Good) since this attribute was not previously captured.
  4. DELETE migrated rows from `inventory_ledger` on success; rollback on any mismatch between expected and actual counts.

- **Endpoint Rewrite**: Modified `/api/inventory/confirm` in `wsgi_handler.py`. The endpoint now:
  1. Reads the source `inventory_ledger` row to pull the flag-time snapshot values.
  2. Locks `prep_fee_at_purchase` from current Settings.
  3. Inserts into `confirmed_buys`, copying snapshots and storing user-supplied condition, buy_cost, quantity, purchase_date, and optional `buyer_order_id`.
  4. Inserts into `confirmed_buy_units` only if a SKU was provided.
  5. DELETEs the source `inventory_ledger` row.

  All inside a single transaction using Python's implicit transaction handling (`conn.commit()` / `conn.rollback()`), to avoid the "cannot start a transaction within a transaction" error that arises from mixing raw `BEGIN TRANSACTION` SQL with sqlite3's autocommit mode.

- **Dismiss Endpoint Fix**: Replaced `UPDATE ... SET status='DISMISSED'` with `DELETE` on `/api/inventory/dismiss` to keep `inventory_ledger` free of soft-deleted noise.

- **Modal UX**: Updated the Confirm Purchase modal in `templates/tracking.html`:
  - Added Condition dropdown (1 = New through 6 = Collectible, defaulting to 4 = Used - Good).
  - Added optional Amazon.com Purchase Order # field (`buyer_order_id`).
  - Added field reset logic so the modal repopulates correctly on each open.
  - Marked SKU as optional in both label and placeholder.

- **Settings UX**: Added helper text under the Prep Fee field in `templates/settings.html` clarifying that prep fee adjustments only affect buys confirmed on or after the change — historical rows keep their original prep fee.

## Verification

- Migration ran successfully in production against the live database:
  - Cleaned up 8 DISMISSED tombstones.
  - Migrated 1 manually-purchased row from `inventory_ledger` to `confirmed_buys`.
  - Final state: `inventory_ledger` has 202 Imported/PURCHASED rows + 8 Dashboard/POTENTIAL rows; `confirmed_buys` has 1 row.
- End-to-end smoke test passed: confirmed a Potential Buy via the modal; verified the new row appeared in `confirmed_buys` with the correct condition, buy_cost, and locked-in prep_fee_at_purchase; verified the source row was deleted from `inventory_ledger`.
- All required code review fixes were applied across four review rounds before final acceptance.

## Issues Encountered

- **Round 1 review** caught that the discriminator `source='Dashboard' AND status='PURCHASED'` correctly distinguishes manually-confirmed rows from SP-API rows, but the migration hardcoded condition to `'1'` (New) when most paperback arbitrage is `'4'` (Used - Good).
- **Round 2 review** caught: modal field reset missing, schema mismatch (`BOOLEAN` vs `INTEGER`) on `snapshot_shipping_included`, SKU still required by endpoint, Dismiss still UPDATE instead of DELETE, and missing tombstone cleanup.
- **Round 3 review** caught the transaction nesting error: raw `conn.execute("BEGIN TRANSACTION")` SQL conflicts with Python's implicit transaction. Fixed by switching to `conn.commit()` / `conn.rollback()`.
- **Round 4 review** caught: `confirmed_buys` table was never created on app startup. Fixed by adding both new table-creation functions to the WSGI initialization block AND to the migration script itself (self-sufficient).
- **Production deploy bug**: `NameError: name 'create_confirmed_buys_table_if_not_exists' is not defined`. Function calls were added to the WSGI startup block but the import statement at the top of `wsgi_handler.py` was not updated. Patched on the server to unblock; needs to be reflected in the repo.

## Status

Success. Card 2 deployed to production. Confirmed Buys ledger is now populated, dual-write collision is eliminated, and the Confirm flow works end-to-end. The new tab UI to surface this data is tracked separately as Card 3.