# Fix FBA Inventory Sync Issue - Iteration 6

## Overview
The diagnostic tool confirmed that permissions are correct and the FBA report contains data (`GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` passed). However, the application still fails to sync this data ("No active inventory found").

## Investigation
*   A debug script simulating the exact report content (with potential tab/spacing issues from the preview) confirmed that Python's `csv.DictReader` correctly identifies the `afn-fulfillable-quantity` column. This rules out a simple parsing error with standard CSV libraries.
*   However, the diagnostic preview showed some "merged" headers (e.g., `mfn-fulfillable-quantitafn-listing-exists`), suggesting potential delimiter or encoding issues (e.g., UTF-8 vs UTF-8-BOM) in the actual report file that might be causing subtle failures in the production environment.

## Resolution
1.  **Proactive Parsing Fixes:** Updated `keepa_deals/inventory_import.py` to:
    *   Explicitly handle `utf-8-sig` (BOM) decoding, which is common in Amazon reports and can break the first column header if not handled.
    *   Strip whitespace from all CSV header keys to handle potential formatting anomalies.
    *   Retained robust logging to capture the exact headers the system sees.

2.  **Diagnostic Tools:** Created two new scripts for the user to run:
    *   `Diagnostics/debug_csv_parsing.py`: Verifies CSV parsing logic with the specific data seen in the user's environment.
    *   `Diagnostics/dump_inventory_ledger.py`: Inspects the actual database state to definitively check if items are being inserted (perhaps with 0 quantity) or if the insert is failing entirely.

## User Action Required
1.  **Run `Diagnostics/debug_csv_parsing.py`:** This will confirm if the parsing logic works with the data structure we believe Amazon is sending.
2.  **Run `Diagnostics/dump_inventory_ledger.py`:** This is critical. It will tell us if the database is empty or if it contains items with `quantity_remaining = 0`.
3.  **Run Sync Again:** The proactive parsing fixes (BOM handling) might have solved the issue invisibly. Try the "Sync from Amazon" action one more time.
