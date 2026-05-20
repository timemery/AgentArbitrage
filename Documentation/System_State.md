
### Tracking API Architecture
The inventory and sales data in `tracking.html` is retrieved via paginated endpoints (`/api/tracking/active`, `/api/tracking/sales`) rather than a monolithic load, to ensure scalability.
- **Active Inventory:** Includes Fulfillable, Inbound Working, Inbound Shipped, and Inbound Receiving quantities.
- **Sales History:** Fetches orders and order items from SP-API, storing them in `sales_ledger`.
- **UI:** The Tracking page shares the same visual style (`strategies-table`, dark theme) as the Dashboard.

### Dashboard Notification Logic
The 'New Deals Found' notification relies on comparing the polled filtered count against a local baseline. The baseline (`currentTotalRecords`) must be set to `data.pagination.total_records` (filtered) rather than `total_db_records` (raw), and must explicitly check for `undefined` to handle valid `0` counts.

### Inferred True Sales Logic (March 2026 Update)
To ensure absolute accuracy, fallback logic estimating list prices via Keepa Stats (listing averages) was entirely removed from `keepa_deals/stable_calculations.py`.
The system now enforces two strict rules to prevent artificial inflation:
1. It requires at least 1 actual inferred sale (correlating an offer drop with a rank drop) to compute a price. Sparse sales (1-2 events) are permitted via their median.
2. An absolute hard ceiling automatically rejects any calculated list price exceeding $1,500, preventing runaway algorithmic math.
Do not reintroduce fallback logic based on listing prices, as it compromises the core promise of only providing true deals.

### Dynamic ROI Calculation
ROI is not a database column. It is calculated dynamically (`(Profit / All_in_Cost) * 100`) on the frontend for display and in backend SQL queries for sorting. `All-in Cost` strictly excludes Amazon fees to ensure this calculation remains accurate.
