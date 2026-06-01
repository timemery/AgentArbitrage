```
# Dev Log: Editable SKU on Confirmed Buys Tab
**Date:** 2026-05-31

## Overview
The goal of this task was to make the SKU field editable within the "Confirmed Buys" tab on the tracking dashboard. According to the build specification for v1 (single-unit case), the SKU is stored in the `confirmed_buy_units` child table, not the `confirmed_buys` parent table. This required the creation of a `PATCH` endpoint capable of updating an existing child row or inserting a new one if it did not yet exist. It also required handling the unique constraint on the `sku` column and updating the UI to support inline editing and error surfacing.

## Challenges Faced
1. **Handling Parent-Child Data Relationships**: Because the SKU lives on the child table (`confirmed_buy_units`), the backend could not simply execute a flat `UPDATE` query. It needed to differentiate between an update to an existing linked unit and the creation of a new unit link if the SKU was being added for the first time.
2. **Handling Unique Constraints**: The `confirmed_buy_units.sku` column has a strict `UNIQUE` index. If a user entered an SKU that was already assigned to another unit, the system would throw a `sqlite3.IntegrityError`. Unhandled, this would result in a generic 500 Internal Server Error, degrading the user experience.
3. **Frontend Data Reversion**: In the event of a validation failure (like a duplicate SKU), the optimistic input field needed to revert to its last known good state to prevent the user from thinking the invalid change was saved.

## Solutions Implemented
- **New PATCH Endpoint**: Created `/api/tracking/confirmed/<int:item_id>/sku` in `wsgi_handler.py`.
- **Conditional Upsert Logic**: Implemented an atomic transaction that queries for an existing `confirmed_buy_units` row. 
  - If a row exists, it executes an `UPDATE` (allowing `NULL` values if the user clears the input).
  - If no row exists and the provided SKU is non-null, it executes an `INSERT`.
- **Constraint Handling**: Wrapped the database execution in a `try...except sqlite3.IntegrityError` block. When triggered, it intercepts the error and returns a clear `409 Conflict` response: `{'error': 'SKU is already in use by another unit.'}`.
- **UI Enhancements**: 
  - Replaced the static table cell in `templates/tracking.html` with an interactive `<input type="text">` styled consistently with the application's `.tidy-input` class.
  - Added an `onblur` event listener that calls a new async `updateConfirmedSku` JavaScript function.
  - Designed the JS function to check for the `409` status code. On failure, it fires a browser alert with the specific error message and immediately calls `fetchConfirmed()` to refetch and revert the input field to the valid state from the database.

## Status
**Success.** The feature works as expected in the single-unit v1 case, properly managing the parent-child table relationship and gracefully rejecting duplicate SKUs without triggering server faults. All Playwright UI tests and core application tests passed successfully.
```

If there is anything else you'd like me to add or modify, please let me know!