# 2026-02-21 Profit & Inventory Tracking - Status Report

## Overview
This task aimed to implement "Profit & Inventory Tracking" features, including:
1.  **Matched Ledger:** Database tables for tracking inventory (`inventory_ledger`) and sales (`sales_ledger`).
2.  **Potential Buy Workflow:** UI to record "Potential Buys" from the Dashboard before purchasing.
3.  **Active Inventory Sync:** Importing existing Amazon inventory via SP-API Reports.
4.  **Manual Auth:** Fixing the MD9100 OAuth error for Private Apps by adding a manual token update form.

## Completed Work
-   **Database:** Created `inventory_ledger`, `sales_ledger`, and `reconciliation_log` tables.
-   **Backend:** Implemented `inventory_import.py` to fetch `GET_MERCHANT_LISTINGS_ALL_DATA` reports.
-   **API:** Added endpoints for inventory management (`/api/inventory`).
-   **Frontend:** Created `tracking.html` and updated `settings.html` with the Manual Credentials form.
-   **Fix:** Resolved the MD9100 error by allowing manual token entry, bypassing the broken OAuth flow.

## Current Blocker: "No Active Inventory Found"
Despite successful token updates (green "Connected" status), the **Sync from Amazon** action returns "No active inventory found."

### Diagnostic Findings
-   The user ran the `Diagnostics/check_inventory_permissions.py` script but encountered an error: `ERROR: Missing Credentials in environment variables.`
-   This confirms the diagnostic script relies on *exported* environment variables, which were not present in the user's shell session when running the script manually.
-   The user provided their `.env` credentials in the chat.

### Hypothesis
1.  **Permission Delay:** Amazon IAM roles can take up to 15-60 minutes to propagate after being added in Seller Central.
2.  **Wrong Role:** The token might still lack the specific `Inventory and Order Tracking` role, or the Report Type requested (`GET_MERCHANT_LISTINGS_ALL_DATA`) requires a different permission set for this specific account type (e.g., FBA vs FBM).
3.  **Empty Report:** The report might be generating successfully (202 Accepted) but returning *empty data* if the account has no *Merchant Fulfilled* inventory (if the report defaults to FBM) or no active listings.

## Next Steps for New Agent
1.  **Run Diagnostic Correctly:** Run `Diagnostics/check_inventory_permissions.py` *with* the credentials exported in the environment to confirm the HTTP status code (403 vs 202).
2.  **Debug Report Content:** If 202 Accepted, modify the script to *download and print* the report content to see if it's truly empty or just parsing incorrectly.
3.  **Check FBA vs FBM:** The current report request uses default parameters. Ensure it includes FBA inventory (`AFN`) if that is the user's primary stock.
