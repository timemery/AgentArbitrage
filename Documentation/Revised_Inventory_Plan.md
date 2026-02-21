# Profit & Inventory Tracking (Revised)

## 1. Executive Summary

This feature introduces a "Matched Ledger" system to track Realized Profit, with a specific focus on a "Potential Buy" workflow that mirrors industry-standard scouting apps (like InventoryLab's Scoutify). This minimizes friction at the point of decision (the "Buy" button) while ensuring accurate data is captured later when the purchase is confirmed.

**Update:** This plan now includes a dedicated strategy for onboarding users with existing large Amazon catalogs, ensuring they can transition seamlessly into Agent Arbitrage without data loss or manual entry overload.

## 2. Competitive Analysis & Design Rationale

A review of competitor workflows (InventoryLab, ScoutIQ, SellerLegend) reveals a standard pattern:

1.  **Separation of Scouting vs. Inventory:** Scouting apps create a "Buy List" (Potential) which is later "Imported" to become active inventory.
2.  **Low Friction Capture:** The initial "Add to List" action is nearly instantaneous to avoid slowing down the sourcing workflow.
3.  **Confirmation Step:** Costs and quantities are finalized only after the physical purchase is made.

**Our Approach:** We will integrate this "Buy List" concept directly into the Dashboard. Clicking "Buy" creates a "Potential" record. The user then confirms this record in the Tracking page to move it to "Active Inventory". This removes the need for external CSV exports/imports common in other tools.

## 3. Conceptual Model: The "Matched Ledger"

The system relies on three stages:

1.  **Potential Buy (Staging):** Items the user clicked "Buy" on.
    *   *Status:* `POTENTIAL`
    *   *Data:* Mutable (Price/Qty can change).
2.  **Active Inventory (Confirmed):** Physical items purchased.
    *   *Status:* `PURCHASED`
    *   *Data:* Immutable Cost Basis.
3.  **Sales Ledger (Automated):** Items sold on Amazon (via SP-API).
4.  **Reconciliation:** Matching Sales to Active Inventory (FIFO).

## 4. Database Schema (`deals.db`)

### A. `inventory_ledger`

Tracks items from "Potential" to "Sold".

```sql
CREATE TABLE inventory_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT NOT NULL,
    title TEXT,
    sku TEXT, -- Critical for matching existing inventory
    purchase_date TIMESTAMP, -- Nullable for Potential/Imported
    buy_cost REAL, -- Nullable for Potential/Imported
    quantity_purchased INTEGER DEFAULT 1,
    quantity_remaining INTEGER DEFAULT 0,
    status TEXT DEFAULT 'POTENTIAL', -- 'POTENTIAL', 'PURCHASED', 'SOLD_OUT', 'DISMISSED'
    source TEXT, -- e.g., "Dashboard", "Imported"
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_inv_asin ON inventory_ledger(asin);
CREATE INDEX idx_inv_sku ON inventory_ledger(sku); -- Added index for SKU lookups
CREATE INDEX idx_inv_status ON inventory_ledger(status);
```

### B. `sales_ledger`

Tracks orders fetched from Amazon.

```sql
CREATE TABLE sales_ledger (
    amazon_order_id TEXT PRIMARY KEY,
    asin TEXT,
    sku TEXT,
    sale_date TIMESTAMP NOT NULL,
    sale_price REAL,
    amazon_fees REAL,
    quantity_sold INTEGER NOT NULL,
    order_status TEXT,
    reconciliation_status TEXT DEFAULT 'UNMATCHED',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_sales_asin ON sales_ledger(asin);
```

### C. `reconciliation_log`

Links specific inventory units to specific orders.

```sql
CREATE TABLE reconciliation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_ledger_id TEXT NOT NULL,
    inventory_ledger_id INTEGER NOT NULL,
    quantity_matched INTEGER NOT NULL,
    realized_profit REAL,
    match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sales_ledger_id) REFERENCES sales_ledger(amazon_order_id),
    FOREIGN KEY(inventory_ledger_id) REFERENCES inventory_ledger(id)
);
```

## 5. Amazon SP-API Integration Requirements

*   **Scopes:** `sellingpartnerapi::orders`, `sellingpartnerapi::listings` (or Reports).
*   **Tasks:**
    *   `fetch_amazon_orders`: Standard order fetching.
    *   `reconcile_inventory`: FIFO matching.
    *   **NEW:** `import_existing_inventory`: Bulk fetch of current stock.

## 6. UI/UX Design

### A. Dashboard "Buy" Workflow (The "Potential" Click)

*   **Action:** User clicks "Buy" on the Dashboard grid.
*   **System Behavior:**
    1.  **Immediate:** Opens Amazon product page in a new tab (non-blocking).
    2.  **Background:** Sends AJAX POST to `/api/inventory`.
    3.  **Data Saved:** ASIN, Title, Current Price (as estimated cost), Status = `POTENTIAL`.
    4.  **Feedback:** Button changes briefly (e.g., "Saved to Tracking") or shows a toast notification, but does *not* show a modal blocking the user.

### B. Tracking Page (`/tracking`)

Features a new "Workflow" based tab structure:

#### Tab 1: Potential Buys (The Inbox)

*   **Purpose:** Review items clicked on the dashboard.
*   **Columns:** Image, Title, ASIN, Est. Cost, Date Clicked.
*   **Actions:**
    *   **"Confirm Purchase" (Primary):** Opens modal to edit/confirm `Buy Cost`, `Qty`, `SKU`, and `Purchase Date`. Changes status to `PURCHASED`.
    *   **"Delete/Dismiss" (Secondary):** User decided not to buy. Changes status to `DISMISSED` (soft delete) or deletes row.

#### Tab 2: Active Inventory (The Assets)

*   **Purpose:** Manage confirmed stock.
*   **Display:** Items with status `PURCHASED` and `quantity_remaining > 0`.
*   **Add:** Visual indicator for items with "Missing Cost" (Red warning text).
*   **Add:** "Bulk Edit Costs" button to handle imported inventory.
*   **Calculations:** Total Asset Value.

#### Tab 3: Sales & Profit (The Scoreboard)

*   **Purpose:** View P&L.
*   **Display:** Matched Sales (Green) and Unmatched Sales (Red warning).
*   **Action:** Unmatched sales allow "Add Missing Cost" which creates a retroactive `PURCHASED` record.

## 7. Onboarding & Migration Strategy (New Section)

Handling users with pre-existing catalogs (1,000+ items):

### A. The "Initial State" Problem
New users arrive with inventory physically at Amazon (or FBM) but with no record in our database. We cannot calculate profit for these items until we know their *Buy Cost*.

### B. Bulk Import Workflow
1.  **Trigger:** User clicks "Sync Amazon Inventory" in Settings.
2.  **Mechanism (Backend):**
    *   Uses SP-API **Reports API** (`GET_MERCHANT_LISTINGS_ALL_DATA`) rather than per-item APIs to handle scale efficiently.
    *   Parses the report to extract ASIN, SKU, Title, and Quantity.
    *   Inserts records into `inventory_ledger` with:
        *   `status` = 'PURCHASED'
        *   `source` = 'Imported'
        *   `buy_cost` = `NULL`
        *   `purchase_date` = `NULL` (or Import Date)
3.  **Mechanism (Frontend):**
    *   **"Missing Costs" Alert:** The Tracking page displays a prominent banner: "Action Required: X items are missing buy costs."
    *   **CSV Cost Injection:** Provide a simple CSV export/import tool:
        *   *Export:* CSV with columns `SKU`, `Title`, `ASIN`.
        *   *User Action:* Fills in `Buy Cost` and `Purchase Date` (optional) in Excel/Sheets.
        *   *Import:* Updates the DB records matching on `SKU`.

## 8. Potential Hurdles & Risks (New Section)

### A. Scale & API Throttling
*   **Risk:** A user with 50,000 books will time out a synchronous API call.
*   **Mitigation:** The Import must be a background Celery task using the Reports API (asynchronous), which is designed for bulk data. The UI must show a "Sync in Progress" state.

### B. SKU Mismatches & Duplicates
*   **Risk:** Users might have the same ASIN listed multiple times with different SKUs (e.g., "Good" vs "Acceptable").
*   **Mitigation:** The system must treat `SKU` as the unique identifier for inventory, not `ASIN`. The schema update to index `sku` supports this.

### C. Retroactive Sales vs. Going Forward
*   **Risk:** User expects to see profit for items sold *last month*.
*   **Decision:** Scope is strictly **"Go Forward"**. We will import *current* inventory. Backfilling historical orders + historical costs is complex and error-prone (matching specific units to specific past orders). We will explicitly communicate that profit tracking begins from the "Day of Import".

### D. "Stranded" or Unfulfillable Inventory
*   **Risk:** Importing items that are at Amazon but damaged/unfulfillable might clutter the view.
*   **Mitigation:** The Report parser should filter for `disposition` = 'SELLABLE' to keep the ledger clean.

## 9. Integration & Coexistence Strategy (Crucial Update)

### A. The "Single Token" Architecture
We currently use SP-API for "Gating Checks" (Restrictions), storing credentials in the `user_credentials` table. The new Inventory features must **share** this same credential storage. We will not create a parallel auth system.

### B. Scope Management & Migration
*   **Current State:** Existing tokens likely only have `listings` scope.
*   **Requirement:** New features require `sellingpartnerapi::orders` (for Sales) and `sellingpartnerapi::reports` (for Inventory Import).
*   **Migration Path:**
    *   The "Connect Amazon" OAuth URL must be updated to request *all* scopes.
    *   **Existing Users:** Will encounter 403 errors on the new features. We must implement a "Re-authorization Required" detection logic. If an API call fails due to missing scopes, the UI must prompt the user to "Update Permissions" (re-run the Connect flow).

### C. Code Refactoring (Shared Auth)
*   **Problem:** `_refresh_sp_api_token` is currently buried inside `sp_api_tasks.py`.
*   **Solution:** Move this logic to `keepa_deals/amazon_sp_api.py` (or a new `sp_api_auth.py`) so it can be imported by:
    1.  `sp_api_tasks.py` (Gating)
    2.  `inventory_import.py` (Bulk Import)
    3.  `order_fetcher.py` (Sales Tracking)

This ensures all features use the same token management and refresh logic.

## 10. Implementation Steps for Agent

1.  *Update `keepa_deals/db_utils.py` to include schema definitions.*
    -   Add `create_inventory_ledger_table`, `create_sales_ledger_table`, and `create_reconciliation_log_table` functions with the specified SQL.
    -   Ensure `sku` is indexed in `inventory_ledger`.
2.  *Verify the new schema.*
    -   Create and run a script `verify_schema_update.py` to check that the new tables exist in `deals.db` (or dev db) with the correct columns.
3.  *Implement Backend Logic for Inventory Import.*
    -   Create `keepa_deals/inventory_import.py` to implement the `fetch_existing_inventory_task` using the SP-API Reports interface (`GET_MERCHANT_LISTINGS_ALL_DATA`).
    -   Implement the CSV parsing logic for bulk cost updates in this file.
    -   Update `wsgi_handler.py` to expose the API endpoints:
        -   `POST /api/inventory/import` (Trigger SP-API sync)
        -   `POST /api/inventory/upload-costs` (CSV Upload)
4.  *Implement Frontend UI.*
    -   Create `templates/tracking.html` to implement the UI for the Potential Buys, Active Inventory, and Sales tabs.
    -   In the `active_inventory` tab, implement the "Missing Cost" warning banner and the "Bulk Edit" button.
    -   Update `wsgi_handler.py` to serve the `/tracking` route.
5.  *Refactor SP-API Auth Logic.*
    -   Move `_refresh_sp_api_token` from `keepa_deals/sp_api_tasks.py` to `keepa_deals/amazon_sp_api.py` or a shared utility.
    -   Update `keepa_deals/sp_api_tasks.py` to use the shared function.
    -   Update `keepa_deals/inventory_import.py` and `keepa_deals/order_fetcher.py` to use the shared function.
6.  *Complete pre commit steps*
    -   Complete pre commit steps to make sure proper testing, verification, review, and reflection are done.
7.  *Submit the changes.*
    -   Submit the changes with a descriptive commit message.
