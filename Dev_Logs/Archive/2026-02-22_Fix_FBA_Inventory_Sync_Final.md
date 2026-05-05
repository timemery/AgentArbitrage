# Fix FBA Inventory Sync Issue - Comprehensive Summary

## Overview
The "Sync from Amazon" feature, critical for the Profit & Inventory Tracking module, was reporting "No active inventory found" for FBA users despite valid Amazon SP-API connections. This blocked users from importing their existing stock and reconciling costs.

## Root Cause Analysis
The failure was due to a combination of four distinct issues:
1.  **Wrong Data Source:** The system relied solely on the `GET_MERCHANT_LISTINGS_ALL_DATA` report. While this report lists all items (FBA and MFN), it frequently reports a quantity of `0` for FBA items, as it is not the authoritative source for FBA stock levels.
2.  **Missing Celery Configuration:** The `keepa_deals.inventory_import` module was not listed in `celery_config.py`. Consequently, the Celery background worker did not register the `fetch_existing_inventory_task`, causing it to silently ignore the sync requests triggered from the UI.
3.  **Diagnostic Failures:** The `check_inventory_permissions.py` diagnostic script failed to run because it expected environment variables (`.env`) which are not updated by the "Manual Credentials Update" UI feature (which saves to the database). It also falsely flagged `GET_AFN_INVENTORY_DATA` as a failure (403 Forbidden) due to missing roles, adding noise.
4.  **Parsing Fragility:** Diagnostic previews revealed potential "merged headers" or whitespace issues in the raw CSV reports from Amazon, which posed a risk of data parsing failures.

## Resolution
### 1. Multi-Report Sync Strategy
*   Modified `keepa_deals/inventory_import.py` to fetch **two** reports:
    *   `GET_MERCHANT_LISTINGS_ALL_DATA`: Used to populate the catalog (ASIN/Title) and sync Merchant-Fulfilled (MFN) inventory.
    *   `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA`: Used as the **authoritative source** for FBA stock levels (`afn-fulfillable-quantity`).
*   Implemented "Smart Merge" logic: The importer inserts items found in the Merchant report but **does not** overwrite existing FBA quantities with `0`. It then updates FBA items with the accurate counts from the FBA MYI report.

### 2. Operational Fix (Celery)
*   Added `'keepa_deals.inventory_import'` to the `imports` tuple in `celery_config.py`. This ensures the background worker correctly registers and executes the inventory sync task.

### 3. Reliability & Hardening
*   **Retry Logic:** Added a retry loop (3 attempts with backoff) for report generation to handle intermittent `CANCELLED` or `FATAL` statuses from the SP-API.
*   **Parsing Hardening:** Updated the CSV parser to:
    *   Decode content using `utf-8-sig` to handle Byte Order Marks (BOM).
    *   Aggressively strip whitespace from all header keys and value columns (SKU/ASIN) to prevent "silent" mismatches (e.g., `"SKU "` vs `"SKU"`).

### 4. Diagnostic Tooling Improvements
*   Updated `Diagnostics/check_inventory_permissions.py` to:
    *   Automatically load `.env` variables.
    *   **Fallback to Database:** If env vars are missing, it retrieves credentials from the `user_credentials` table, aligning with the Private App workflow.
    *   Removed the problematic `GET_AFN_INVENTORY_DATA` check.
    *   Added logic to download and preview the first 5 lines of the report to verify data availability.
*   Created `Diagnostics/debug_csv_parsing.py` and `Diagnostics/dump_inventory_ledger.py` for granular troubleshooting.

## Verification
*   **Unit Tests:** Updated `tests/test_inventory_import.py` to simulate the multi-report flow, verifying that an FBA item initialized with Qty 0 (from Merchant report) is correctly updated to Qty 10 (from FBA report).
*   **User Validation:** The user confirmed that "Sync from Amazon" now successfully populates the "Active Inventory" table with correct quantities (e.g., Qty 1) and status.

## Future Recommendations
*   **Sales Sync:** The current task focused on *Inventory*. The next logical step is to implement the *Sales Ledger* sync to match "Sold" items against this inventory.
*   **Cost Reconciliation:** The imported items currently show "Cost: Missing". Users will need to use the "Upload Costs" feature or manual editing to complete the profit analysis.
