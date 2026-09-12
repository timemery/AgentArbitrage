
### Tracking API Architecture
The inventory and sales data in `tracking.html` is retrieved via paginated endpoints (`/api/tracking/active`, `/api/tracking/sales`) rather than a monolithic load, to ensure scalability.
- **Active Inventory:** Includes Fulfillable, Inbound Working, Inbound Shipped, and Inbound Receiving quantities. It queries the `inventory_ledger` which natively stores the `asin` column, enabling direct product identification on the frontend without complex JOINs.
- **Sales History:** Fetches orders and order items from SP-API, storing them in `sales_ledger`.
  - *Note on Fees:* The "Fees (Est)" column was removed from the Sales & Profit tab because the SP-API Orders v0 endpoint does not return fee data (this requires a separate Finances API integration). Instead, Realized Profit is dynamically estimated on the backend using the same profit calculation logic as the Deals dashboard (merging the realized `sale_price` from `sales_ledger` with the original `buy_cost_paid` from `inventory_ledger` via FIFO matching).
- **Potential Buys & Editable Costs:** The system supports inline editing of the `buy_cost_paid` for "Potential Buys". When a user edits a buy cost, the `buy_cost_confirmed` boolean flag is set to TRUE in the `inventory_ledger`. This enables precise frontend inline recalculations of exact all-in costs and realized ROI, replacing initial system estimates prior to actual purchase. Unconfirmed estimates are visually distinguished to ensure users verify them.
- **UI:** The Tracking page shares the same visual style (`strategies-table`, dark theme) as the Dashboard. It implements client-side sorting matching Dashboard behavior, with sticky headers and a scroll-triggered shadow mask. Identifiers (ASIN, SKU, Order ID) are rendered as hyperlinks to Amazon and Seller Central. Pagination logic has been unified into a shared component (`static/js/pagination.js`) handling both Dashboard and Tracking data formats. CSV-related actions on the Active Inventory tab are demoted behind a 'Bulk edit via CSV' expandable link to declutter the primary UI.

### Dashboard Notification Logic
The 'New Deals Found' notification relies on comparing the polled filtered count against a local baseline. The baseline (`currentTotalRecords`) must be set to `data.pagination.total_records` (filtered) rather than `total_db_records` (raw), and must explicitly check for `undefined` to handle valid `0` counts.

### Inferred True Sales Logic (March 2026, completed September 2026)
To ensure absolute accuracy, fallback logic estimating list prices via Keepa Stats (listing averages) was removed from `keepa_deals/stable_calculations.py` in March 2026.

**That removal was incomplete.** A second fallback survived in `keepa_deals/new_analytics.py` on the `1yr. Avg.` path, taking the **maximum** of five `avg365` condition tiers, and went on firing for six months. It was removed on **2026-09-11** (audit item B-6). Zero inferred sales inside the last 365 days now returns `None`, on every price path. A new `Inferred_Sale_Count` column records how many sane sale events each price actually rests on.


The system now enforces two strict rules to prevent artificial inflation:
1. It requires at least 1 actual inferred sale (correlating an offer drop with a rank drop) to compute a price. Sparse sales (1-2 events) are permitted via their median.
2. An absolute hard ceiling automatically rejects any calculated list price exceeding $1,500, preventing runaway algorithmic math.
Do not reintroduce fallback logic based on listing prices, as it compromises the core promise of only providing true deals.

### Price Association Fix (September 2026)
The price attached to an inferred sale is now the last history point **strictly before** the offer drop, at **any** distance. `merge_asof(direction='backward', allow_exact_matches=False)` in `keepa_deals/stable_calculations.py`.

`csv[1]` / `csv[2]` hold the **lowest** New / Used offer price, not any one copy's price, so when the cheapest copy sells the series steps **up** to the next cheapest listing at essentially the same timestamp. The previous `merge_asof(direction='nearest')` had no tie-break and recorded that asking price on **5 of 7 sales across 3 ASINs** measured live on 2026-09-11 ($124.85 stored as $1,000.00, $49.95 as $499.95, $328.19 as $625.59). 4 of those 7 had a price point on the exact minute of the drop, so `allow_exact_matches=False` does most of the work.

**No time threshold, by owner decision on measured data (2026-09-12).** A 240h tolerance was proposed and rejected: the real preceding-gaps were 3.0, 5.1, 10.2, 252.1, 389.6, 516.4 and 2281.4 hours, bimodal with nothing between 10h and 252h, so the threshold would have discarded 4 of 7 true sales. The series is a change-log, so a long gap means the lowest offer had not changed and the distant point is correct. A stale-price guard, if ever wanted, needs continuity of the series across the gap rather than gap length; that is an open item. Because 0 of 7 drops lacked a prior point, `Deal Trust` and xAI-rescue traffic are effectively unchanged by this fix.

**Heavy path only, and it repairs nothing.** Only newly discovered deals are affected — the light path never recomputes `List_at` or `1yr_Avg`, and `recalculator.py` is API-free. Rows written under the old association keep their inflated values until a heavy re-fetch replaces them. Recovery is a separate, open decision.

### Dynamic ROI Calculation
ROI is not a database column. It is calculated dynamically (`(Profit / All_in_Cost) * 100`) on the frontend for display and in backend SQL queries for sorting. `All-in Cost` strictly equals `buy_cost_paid` + prep fee, and excludes Amazon fees to ensure this calculation remains accurate.

### Smart Ingestion & Token Rate Adaptation (August 2026 Update)
To resolve task livelocks under upgraded Keepa API plans (e.g. 25 tokens/min):
1. **5-Minute Ingestion Interval:** `smart-ingestor-run` in `celery_config.py` runs every **5 minutes** (`crontab(minute='*/5')`). This prevents 1-minute `TokenRechargeError` loops and giant log file bloat.
2. **Granular Burst Threshold:** `TokenManager.BURST_THRESHOLD` is capped at **50 tokens** for high refill rates (>= 20/min) and **40 tokens** for lower rates (< 20/min).
3. **Low-Cost Buffer Exit:** For low-cost API calls (cost <= 10), Recharge Mode exits as soon as tokens reach **20**, allowing background status and deal checks to proceed without waiting for full bucket refills.
