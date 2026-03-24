
### Tracking API Architecture
The inventory and sales data in `tracking.html` is retrieved via paginated endpoints (`/api/tracking/active`, `/api/tracking/sales`) rather than a monolithic load, to ensure scalability.
- **Active Inventory:** Includes Fulfillable, Inbound Working, Inbound Shipped, and Inbound Receiving quantities.
- **Sales History:** Fetches orders and order items from SP-API, storing them in `sales_ledger`.
- **UI:** The Tracking page shares the same visual style (`strategies-table`, dark theme) as the Dashboard.

### Dashboard Notification Logic
The 'New Deals Found' notification relies on comparing the polled filtered count against a local baseline. The baseline (`currentTotalRecords`) must be set to `data.pagination.total_records` (filtered) rather than `total_db_records` (raw), and must explicitly check for `undefined` to handle valid `0` counts.

### Inferred True Sales Logic (March 2026 Update)
The fallback logic that estimated list prices using Keepa Stats (average listing prices) has been removed from `keepa_deals/stable_calculations.py`. The system now strictly requires at least 1 actual inferred sale to compute a price. This ensures all profits shown on the dashboard are based on true sales, addressing concerns about elevated artificial list prices. Sparse sales (1-2 true sales) will still compute a price based on their median. Do not reintroduce fallback logic based on listing prices, as it compromises the system's accuracy.
