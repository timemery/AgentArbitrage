
### Tracking API Architecture
The inventory and sales data in `tracking.html` is retrieved via paginated endpoints (`/api/tracking/active`, `/api/tracking/sales`) rather than a monolithic load, to ensure scalability.
- **Active Inventory:** Includes Fulfillable, Inbound Working, Inbound Shipped, and Inbound Receiving quantities. It queries the `inventory_ledger` which natively stores the `asin` column, enabling direct product identification on the frontend without complex JOINs.
- **Sales History:** Fetches orders and order items from SP-API, storing them in `sales_ledger`.
  - *Note on Fees:* The "Fees (Est)" column was removed from the Sales & Profit tab because the SP-API Orders v0 endpoint does not return fee data (this requires a separate Finances API integration). Instead, Realized Profit is dynamically estimated on the backend using the same profit calculation logic as the Deals dashboard (merging the realized `sale_price` from `sales_ledger` with the original `buy_cost_paid` from `inventory_ledger` via FIFO matching).
- **Potential Buys & Editable Costs:** The system supports inline editing of the `buy_cost_paid` for "Potential Buys". When a user edits a buy cost, the `buy_cost_confirmed` boolean flag is set to TRUE in the `inventory_ledger`. This enables precise frontend inline recalculations of exact all-in costs and realized ROI, replacing initial system estimates prior to actual purchase. Unconfirmed estimates are visually distinguished to ensure users verify them.
- **UI:** The Tracking page shares the same visual style (`strategies-table`, dark theme) as the Dashboard. It implements client-side sorting matching Dashboard behavior, with sticky headers and a scroll-triggered shadow mask. Identifiers (ASIN, SKU, Order ID) are rendered as hyperlinks to Amazon and Seller Central. Pagination logic has been unified into a shared component (`static/js/pagination.js`) handling both Dashboard and Tracking data formats. CSV-related actions on the Active Inventory tab are demoted behind a 'Bulk edit via CSV' expandable link to declutter the primary UI.

### Dashboard Notification Logic
The 'New Deals Found' notification relies on comparing the polled filtered count against a local baseline. The baseline (`currentTotalRecords`) must be set to `data.pagination.total_records` (filtered) rather than `total_db_records` (raw), and must explicitly check for `undefined` to handle valid `0` counts.

### Inferred True Sales Logic (March 2026 Update)
To ensure absolute accuracy, fallback logic estimating list prices via Keepa Stats (listing averages) was entirely removed from `keepa_deals/stable_calculations.py`. 
The system now enforces two strict rules to prevent artificial inflation:
1. It requires at least 1 actual inferred sale (correlating an offer drop with a rank drop) to compute a price. Sparse sales (1-2 events) are permitted via their median.
2. An absolute hard ceiling automatically rejects any calculated list price exceeding $1,500, preventing runaway algorithmic math.
Do not reintroduce fallback logic based on listing prices, as it compromises the core promise of only providing true deals.

### Dynamic ROI Calculation
ROI is not a database column. It is calculated dynamically (`(Profit / All_in_Cost) * 100`) on the frontend for display and in backend SQL queries for sorting. `All-in Cost` strictly equals `buy_cost_paid` + prep fee, and excludes Amazon fees to ensure this calculation remains accurate.
