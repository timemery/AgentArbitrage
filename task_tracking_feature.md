# Feature Specification: Profit & Inventory Tracking

## 1. Executive Summary
This feature introduces a "Matched Ledger" system to track Realized Profit. It solves the core problem that Amazon knows the *Sale Price* but not the *Buy Cost*. By capturing the Buy Cost at the moment of decision (via the Dashboard) and syncing Sales automatically from Amazon, we can provide a seamless, semi-automated P&L experience that is superior to retroactive data entry.

## 2. Conceptual Model: The "Matched Ledger"

The system relies on two primary ledgers and a reconciliation process:

1.  **Inventory Ledger (Manual/User Input):** Records items purchased.
    *   *Source:* "Buy" Button on Dashboard OR Manual "Add Purchase" form.
    *   *Key Data:* ASIN, Buy Cost, Purchase Date, Quantity.
2.  **Sales Ledger (Automated/SP-API):** Records items sold on Amazon.
    *   *Source:* Amazon SP-API (`/orders/v0/orders`).
    *   *Key Data:* Order ID, SKU/ASIN, Sale Price, Fees, Date.
3.  **Reconciliation (FIFO Logic):**
    *   The system runs a background process to match **Sales** to **Inventory** based on ASIN.
    *   It uses **First-In-First-Out (FIFO)**: The oldest inventory unit for ASIN X is matched to the newest sale of ASIN X.
    *   *Result:* A "Matched Transaction" that allows calculating `Realized Profit = Sale Price - Amazon Fees - Buy Cost`.

## 3. Database Schema (`deals.db`)

The following SQLite tables are required:

### A. `inventory_ledger`
Tracks physical items purchased.
```sql
CREATE TABLE inventory_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT NOT NULL,
    title TEXT,
    purchase_date TIMESTAMP NOT NULL,
    buy_cost REAL NOT NULL, -- Cost per unit
    quantity_purchased INTEGER NOT NULL,
    quantity_remaining INTEGER NOT NULL, -- Decrements as items are sold
    source TEXT, -- e.g., "Dashboard Buy Button", "Manual Entry"
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_inv_asin ON inventory_ledger(asin);
```

### B. `sales_ledger`
Tracks orders fetched from Amazon.
```sql
CREATE TABLE sales_ledger (
    amazon_order_id TEXT PRIMARY KEY,
    asin TEXT, -- Derived from OrderItems
    sku TEXT,  -- Derived from OrderItems
    sale_date TIMESTAMP NOT NULL,
    sale_price REAL, -- Total price / quantity
    amazon_fees REAL, -- Estimated or fetched
    quantity_sold INTEGER NOT NULL,
    order_status TEXT, -- Pending, Shipped, Canceled
    reconciliation_status TEXT DEFAULT 'UNMATCHED', -- 'MATCHED', 'PARTIAL', 'UNMATCHED'
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_sales_asin ON sales_ledger(asin);
```

### C. `reconciliation_log`
Links specific inventory units to specific orders to lock in profit calculations.
```sql
CREATE TABLE reconciliation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_ledger_id TEXT NOT NULL, -- FK to sales_ledger.amazon_order_id
    inventory_ledger_id INTEGER NOT NULL, -- FK to inventory_ledger.id
    quantity_matched INTEGER NOT NULL,
    realized_profit REAL, -- Snapshot of profit for this specific match
    match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sales_ledger_id) REFERENCES sales_ledger(amazon_order_id),
    FOREIGN KEY(inventory_ledger_id) REFERENCES inventory_ledger(id)
);
```

## 4. Amazon SP-API Integration Requirements

To automate the Sales Ledger, the system must be upgraded to fetch Orders.

### A. Scope Updates
*   **Current Scopes:** Likely only `listings:items` (based on `check_restrictions`).
*   **Required Scopes:** The Developer Profile / App Authorization must include the **Orders** role (`sellingpartnerapi::orders`).
*   **Action:** User must re-authorize the app with these new permissions.

### B. New Backend Tasks
1.  **`fetch_amazon_orders` (Celery Task):**
    *   Frequency: Every 4-6 hours.
    *   API Endpoint: `GET /orders/v0/orders`.
    *   Params: `CreatedAfter` (Watermark), `OrderStatuses` (Shipped, Pending).
    *   Logic:
        1.  Fetch Orders.
        2.  For each Order, call `GET /orders/v0/orders/{orderId}/orderItems` to get ASIN/SKU and Price details.
        3.  Upsert into `sales_ledger`.
2.  **`reconcile_inventory` (Celery Task):**
    *   Runs after `fetch_amazon_orders`.
    *   Iterates through `UNMATCHED` sales.
    *   Queries `inventory_ledger` for the oldest record with `quantity_remaining > 0` and matching ASIN.
    *   Creates record in `reconciliation_log`.
    *   Updates `quantity_remaining` and `reconciliation_status`.

## 5. UI/UX Design

### A. Dashboard "Buy" Workflow (Capture at Source)
*   **Current Behavior:** "Buy" button links to Amazon.
*   **New Behavior:** Clicking "Buy" opens a **"Log Purchase" Modal**.
    *   **Fields:**
        *   ASIN/Title (Read-only, pre-filled).
        *   Price/Cost (Pre-filled with `Price Now`, editable).
        *   Quantity (Default: 1, editable).
        *   Date (Default: Today).
    *   **Actions:**
        *   "Save & Open Amazon" (Primary): Saves to `inventory_ledger` AND opens the Amazon link in new tab.
        *   "Save Only": Just saves to ledger.
        *   "Cancel": Closes modal.

### B. Tracking Page (`/tracking`)
The page should feature three main tabs:

#### Tab 1: Active Inventory
*   **Display:** Table of `inventory_ledger` items where `quantity_remaining > 0`.
*   **Columns:** Purchase Date, Title, ASIN, Cost, Qty, Age (Days since purchase).
*   **Calculations:** "Total Inventory Value" (Sum of Cost * Qty).
*   **Actions:** Edit Cost, Delete.

#### Tab 2: Sales & Profit
*   **Display:** Table of `sales_ledger` items joined with `reconciliation_log`.
*   **Columns:** Sale Date, Order ID, Title, Sale Price, Buy Cost, Fees, **Net Profit**, **ROI %**.
*   **Highlighting:**
    *   **Green Profit:** Positive return.
    *   **Red Profit:** Negative return.
    *   **Warning Row:** "Unmatched Sale" (Sale exists but no Inventory found). Clicking it prompts to "Add Missing Purchase".

#### Tab 3: Overview (Analytics)
*   **Metrics:**
    *   Total Realized Profit (This Month / All Time).
    *   Average ROI.
    *   Inventory Turnover Rate.
*   **Charts:** Bar chart of Monthly Profit.

## 6. Implementation Steps for Agent

1.  **Database Migration:**
    *   Create the 3 new tables in `deals.db`.
    *   Update `keepa_deals/db_utils.py` to include creation functions.
2.  **Backend - API:**
    *   Create `keepa_deals/sp_api_orders.py` implementing `get_orders` and `get_order_items`.
    *   Create `keepa_deals/order_sync_tasks.py` with the Celery tasks.
    *   Create `keepa_deals/reconciliation.py` with the FIFO logic.
3.  **Backend - Routes:**
    *   Add `/api/inventory` (POST/GET/PUT/DELETE) to `wsgi_handler.py`.
    *   Add `/api/sales` (GET) to `wsgi_handler.py`.
4.  **Frontend - Dashboard:**
    *   Add the "Log Purchase" Modal to `dashboard.html`.
    *   Update `dashboard.js` to handle the "Buy" button click event.
5.  **Frontend - Tracking:**
    *   Implement the Tabbed interface in `tracking.html`.
    *   Write `static/js/tracking.js` to fetch and render the ledgers.
