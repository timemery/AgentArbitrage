# Fix FBA Inventory Sync Issue

## Overview
The "Sync from Amazon" feature was failing to populate "Active Inventory" for FBA users, despite successful SP-API connection. The system reported "No active inventory found".

## Root Cause
The `inventory_import.py` script was relying solely on the `GET_MERCHANT_LISTINGS_ALL_DATA` report. While this report includes FBA items, it typically reports their quantity as `0` (or MFN quantity), as it is primarily a listing report, not an FBA inventory report. The application filters active inventory by `quantity > 0`, causing FBA items to be hidden.

## Resolution
1.  **Dual Report Fetching:** Updated `keepa_deals/inventory_import.py` to fetch a second report type: `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` (FBA Manage Inventory - Unsuppressed).
2.  **Logic Update:**
    *   The import process now iterates through both reports.
    *   The Merchant report is processed first (populating MFN items and FBA items with 0 qty).
    *   The FBA report is processed second, updating the `quantity_remaining` for FBA items with the authoritative `afn-fulfillable-quantity`.
3.  **Diagnostic Tool:** Updated `Diagnostics/check_inventory_permissions.py` to verify permissions for both report types, aiding in future debugging.

## Verification
*   Created a reproduction test `tests/test_inventory_import.py` which confirmed the issue (Merchant report resulting in 0 qty for FBA items).
*   Verified the fix using the same test, confirming that processing the FBA report correctly updates the quantity to the actual stock level (e.g., 10).
