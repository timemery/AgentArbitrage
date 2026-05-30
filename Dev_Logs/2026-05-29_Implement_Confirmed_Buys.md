# Implement Confirmed Buys (Card 2)

## Overview
This task involved implementing the backend schema and endpoint changes required for the Confirmed Buys feature as outlined in `Confirmed_Buys_Build_Spec.md`. The goal is to separate manually purchased items into their own ledger (`confirmed_buys` and `confirmed_buy_units`) and remove them from the `inventory_ledger` to prevent dual-write collisions with the SP-API.

## Actions Taken
- **Schema Update**: Added `create_confirmed_buys_table_if_not_exists` and `create_confirmed_buy_units_table_if_not_exists` to `keepa_deals/db_utils.py` and called them within the initialization logic. The new tables include fields for preserving snapshot financial metrics from Card 1.
- **Data Migration**: Created `migrate_confirmed_buys.py` to identify manual buys (`status = 'PURCHASED'` and `source = 'Dashboard'`) and move them to `confirmed_buys` while deleting them from `inventory_ledger`. Added logic to clean up invalid tombstone items in `inventory_ledger` with `status = 'DISMISSED'`.
- **Endpoint Rewrite**: Modified the `/api/inventory/confirm` route in `wsgi_handler.py`. The endpoint now starts a transaction, inserts a record into `confirmed_buys` alongside capturing fresh prep fees from settings and historical snapshot costs from the `inventory_ledger` row. It then creates a matching `confirmed_buy_units` record (if a SKU was provided) and subsequently deletes the original `inventory_ledger` entry.
- **Bug Fix**: Replaced the previous `UPDATE` operation with `DELETE` on the `/api/inventory/dismiss` endpoint to ensure proper garbage collection of dismissed potential purchases.
- **Settings UX**: Added a trivial but helpful UI string near the prep fee field in `templates/settings.html` to clarify that prep fee adjustments only affect newly confirmed buys.
- **Modal UX**: Added a Condition field drop-down, resetting of fields when the modal is closed, and removed the SKU requirement on `/api/inventory/confirm`.

## Verification
- Verified database initialization locally creates the expected schemas correctly.
- Wrote local test cases (`test_confirm.py` and `test_dismiss.py`) which verified a full run of the rewrite logic handles database transactions effectively: successfully saving to both new schemas and clearing out the source schema on completion. All tests passed.

## Status
Success. The requirements of Card 2 are fulfilled.
