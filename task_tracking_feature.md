# Feature Specification: Profit & Inventory Tracking

## 1. Executive Summary
This feature introduces a "Matched Ledger" system to track Realized Profit, with a specific focus on a "Potential Buy" workflow that mirrors industry-standard scouting apps (like InventoryLab's Scoutify). This minimizes friction at the point of decision (the "Buy" button) while ensuring accurate data is captured later when the purchase is confirmed.

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
    sku TEXT, -- Added: Optional at first, required for specific matching later
    purchase_date TIMESTAMP, -- Nullable for Potential
    buy_cost REAL, -- Nullable/Estimated for Potential
    quantity_purchased INTEGER DEFAULT 1,
    quantity_remaining INTEGER DEFAULT 0,
    status TEXT DEFAULT 'POTENTIAL', -- 'POTENTIAL', 'PURCHASED', 'SOLD_OUT', 'DISMISSED'
    source TEXT, -- e.g., "Dashboard Buy Button"
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_inv_asin ON inventory_ledger(asin);
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
(No changes from previous design, standard Orders API requirements apply).
*   **Scopes:** `sellingpartnerapi::orders`.
*   **Tasks:** `fetch_amazon_orders` (GET /orders/v0/orders), `reconcile_inventory` (Background FIFO matching).

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
*   **Calculations:** Total Asset Value.

#### Tab 3: Sales & Profit (The Scoreboard)
*   **Purpose:** View P&L.
*   **Display:** Matched Sales (Green) and Unmatched Sales (Red warning).
*   **Action:** Unmatched sales allow "Add Missing Cost" which creates a retroactive `PURCHASED` record.

## 7. Implementation Steps for Agent

1.  **Database Migration:** Implement the updated schema (with `status` and `sku`).
2.  **Backend - API:**
    *   Update `/api/inventory` to handle status transitions (`POTENTIAL` -> `PURCHASED`).
    *   Implement SP-API Orders fetcher.
3.  **Frontend - Dashboard:**
    *   Modify "Buy" button JS listener to trigger the "Silent Save" AJAX call.
4.  **Frontend - Tracking:**
    *   Build the "Potential Buys" table with the "Confirm Purchase" modal form.
    *   Build the standard Inventory and Sales tables.
