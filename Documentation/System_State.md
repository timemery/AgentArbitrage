
### Tracking API Architecture
The inventory and sales data in `tracking.html` is retrieved via paginated endpoints (`/api/tracking/active`, `/api/tracking/sales`) rather than a monolithic load, to ensure scalability.
- **Active Inventory:** Includes Fulfillable, Inbound Working, Inbound Shipped, and Inbound Receiving quantities.
- **Sales History:** Fetches orders and order items from SP-API, storing them in `sales_ledger`.
- **UI:** The Tracking page shares the same visual style (`strategies-table`, dark theme) as the Dashboard.

### Dashboard Notification Logic
The 'New Deals Found' notification relies on comparing the polled filtered count against a local baseline. The baseline (`currentTotalRecords`) must be set to `data.pagination.total_records` (filtered) rather than `total_db_records` (raw), and must explicitly check for `undefined` to handle valid `0` counts.
