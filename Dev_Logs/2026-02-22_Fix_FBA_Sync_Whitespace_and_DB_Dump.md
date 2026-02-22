# Fix FBA Inventory Sync Issue - Iteration 7

## Overview
The "Sync from Amazon" feature is failing to update inventory, despite successful report generation. Diagnostic tools revealed:
1.  **Parsing Works:** The CSV parser correctly identifies the critical `afn-fulfillable-quantity` column.
2.  **Database State:** Only **1 row** exists in the `inventory_ledger`, and it likely has a `NULL` or invalid value in one of its columns (causing the dump script to crash).
3.  **Hypothesis:** A subtle mismatch in SKU formatting (e.g., trailing whitespace) between the Merchant report (which inserts the item) and the FBA report (which updates it) might be causing the update to fail or create duplicate/invalid entries. Or, the initial insert from the Merchant report might be flawed.

## Resolution
1.  **Diagnostic Tool Fix:** Updated `Diagnostics/dump_inventory_ledger.py` to handle `None` values gracefully. This is critical. **You must run this script** to see what the single "invisible" row in your database actually is.
2.  **Proactive Hardening:** Updated `keepa_deals/inventory_import.py` to:
    *   **Strip Whitespace:** Automatically strips leading/trailing whitespace from SKU and ASIN values from *both* reports. This ensures `TXT-0123` matches `TXT-0123 `.
    *   **BOM Handling:** Retained `utf-8-sig` handling.

## User Action Required
1.  **Run `Diagnostics/dump_inventory_ledger.py`:** Please run this script again. It will no longer crash. The output will tell us exactly what is in your database (e.g., is the SKU `None`? Is the Quantity `0`?).
2.  **Run Sync Again:** The whitespace fix might have solved the matching issue. Try the "Sync from Amazon" action.
3.  **Share Results:** Please paste the output of the dump script. It is the key to solving this if the sync still fails.
