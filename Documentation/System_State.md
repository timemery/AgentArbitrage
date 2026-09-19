
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

### xAI Sales Rescue Removed (2026-09-16)
A third source of unverified prices outlived both fallback removals above. `infer_sale_events` called `infer_sales_with_xai` on **both** of its zero-sale branches and returned the model's events verbatim into pricing. **Removed by owner decision (Trello #141): zero confirmed sales is now a final answer.**

A model-asserted sale is not an offer drop correlated with a rank drop. It returned *before* the IQR filter and before the `price <= 0` and NaN guards, and the September 2026 price association never applied to it — a rescued price is not read from `csv[1]`/`csv[2]`, it is asserted. Measured in production 2026-08-28 to 2026-09-08: **13 rescues, every one returning exactly 1 sale.** At n=1 the Sparse Sales Rescue takes the median of one number, so `List at` and `1yr. Avg.` became the same single model-asserted figure — and because a rescued event always landed inside 365 days, those rows *always* cleared the dashboard's data-completeness filter. On the failed-correlation branch it also read `Deal Trust` as **1/N** rather than 0%.

Affected rows are **not identifiable by query**: `price_source` was computed but never persisted, so the only markers are the log lines and the weak `List_at == 1yr_Avg` heuristic. Existing rows keep their rescued values until a heavy re-fetch replaces them. `keepa_deals/xai_sales_inference.py` is retained (the dormant `Keepa_Deals.py` path references it) but nothing live calls it; `tests/test_xai_rescue_excluded.py` pins the absence.

### Pricing Logic Version & Repair (September 2026)
`Pricing_Logic_Version` records which pricing logic wrote a row's prices, because **nothing else in the schema does** — `last_seen_utc` and `source` are rewritten by every path, and `Inferred_Sale_Count` is disproved by rows priced between 2026-09-11 and the 09-12 association fix, which carry a count alongside pre-fix prices.

`NULL` or a value below the current `PRICING_LOGIC_VERSION` means **stale pricing, due a heavy re-fetch**. That is a SCHEDULING rule and is deliberately the opposite of the `Inferred_Sale_Count` NULL rule, which governs whether a deal may be shown. There is no backfill.

`repair_pricing.py` is the only way an existing row reaches the heavy path: the Smart Ingestor routes existing ASINs to the light path unconditionally, and the light path, Stale Rescue and recalculator all leave `List_at`/`1yr_Avg` untouched. It repairs visible rows first, then priced rows by `List_at` DESC, then unpriced. Resumption falls out of the predicate — a repaired row carries the current version and stops matching — so an interrupted multi-day run is restarted with the same command.

**A future pricing fix re-uses the same script by bumping the constant.** No new script, no new predicate.

**Running it** (it runs for days; run it detached, as `www-data`):

```bash
cd /var/www/agentarbitrage
# Preview first. A dry run SPENDS Keepa tokens but writes nothing, so --limit is
# REQUIRED - an unbounded dry run is refused outright.
sudo -u www-data venv/bin/python repair_pricing.py --limit 10
# Then let it go.
sudo -u www-data nohup venv/bin/python repair_pricing.py --apply > /dev/null 2>&1 &
tail -f Diagnostics/repair_pricing.log     # progress
pkill -f repair_pricing.py                 # clean stop between batches
```

**Two columns it cannot recompute.** `Deal_found` and `last_price_change` (the dashboard's "Ago") come from the /deal feed object, which the ingestor merges into `product_data` but which cannot be fetched for an arbitrary ASIN. Their stored values are **carried forward** rather than blanked. That is an explicit two-column allowlist established by auditing all 67 non-`None` `FUNCTION_LIST` entries, by source and empirically; every pricing column is still overwritten, including to NULL.

**Rows it cannot repair** — not returned by Keepa, or rejected by heavy processing — are attempted **once per run**, recorded in a separate SKIPPED manifest with a reason, and excluded from later batches so they cannot loop.

**The xAI daily cap, not Keepa tokens, is what makes the sweep take days.** Keepa costs ~7 tokens a row (~42 hours for the whole table), but the sweep makes **~1.7 AI Reasonableness calls per row** — measured 2026-09-17 — most of them *forced* by the 3x-of-current-used rule, which fires on precisely the inflated rows being repaired. Against `max_xai_calls_per_day` (1000, shared with ingestion) that is roughly **500–600 rows a day**, so a full sweep is about **8–10 calendar days** of one run per day.

The sweep **stops itself while the check still works** (`--xai-headroom`, default 50). This is not politeness: past the cap `_query_xai_for_reasonableness` does not fail and does not skip the row — it returns `True` (`stable_calculations.py:76`), so an inflated price would be accepted unchecked *and* stamped `Pricing_Logic_Version = 2`, dropping it out of the predicate so the sweep never revisits it. Continuing past the cap is strictly worse than stopping. The daily count resets on the first call after the **local date changes on the box**, so re-run after local midnight.

It takes its own verified backup through SQLite's backup API before the first write (`backup_db.sh` is a plain `cp` of a WAL database and can be silently short).

**Stop conditions, and the one that is not a stop.** The sweep ends a run cleanly (exit 0, resumable by re-running the same command) when any of these hold, all checked before every batch and before every recharge retry:

| condition | why |
| :--- | :--- |
| spare xAI calls < `--xai-headroom` (default 50) | past the cap the reasonableness check returns `True`, so an unchecked price would be stamped as current and never revisited |
| Keepa refill rate < 20/min | the plan has been downgraded or throttled; continuing would starve normal ingestion |
| `--limit` reached, no stale rows left, or SIGTERM/SIGINT | ordinary completion |
| `--max-recharge-retries` consecutive recharge waits (default 10) | the bucket is not recovering — a stall, not a dip |
| any exception other than `TokenRechargeError` | unchanged: the run stops and nothing in that batch is written |

**A `TokenRechargeError` is NOT a stop.** It is waited out. `TokenManager` raises instead of sleeping whenever the calculated wait exceeds 60s (`token_manager.py:299`, `:440`) so a Celery task can release its lock and free the worker — right for the Smart Ingestor, wrong for a script that holds no lock, has nothing else to do and has no scheduler to bring it back. On 2026-09-17 the live sweep ended after about an hour on `Recharge needed: 130s`, with xAI at 79 of 5000 calls: a 130-second dip in a bucket shared with ingestion ended a run with days left. Keepa refills at 25/min and the sweep reserves 50 tokens a batch, so these dips recur every run.

The sweep now sleeps the seconds the exception asks for plus a 15-second margin, logs each wait, and **retries the same batch from the target list already in memory** — not by re-selecting it, because those ASINs entered the per-run attempted set before the fetch and re-selection would exclude the very rows being retried. The consecutive-wait counter resets on the first batch that gets through, so it bounds a stall rather than a long run.

**When it finishes, refresh Prime Picks** — `prime_picks` caches a selection made against the old prices and is not beat-scheduled, so it will not self-heal.

**Progress:**

```sql
SELECT COALESCE(CAST("Pricing_Logic_Version" AS TEXT), 'NULL (stale)') AS version,
       COUNT(*)                                                        AS rows,
       SUM(CASE WHEN "List_at" > 0 THEN 1 ELSE 0 END)                  AS priced,
       ROUND(AVG(CASE WHEN "List_at" > 0 THEN "List_at" END), 2)       AS avg_list_at,
       SUM(CASE WHEN "List_at" >= 1000 THEN 1 ELSE 0 END)              AS four_figure
FROM deals GROUP BY 1 ORDER BY 1;
```

Baseline at 2026-09-16: 4,534 rows, 3,070 priced, 1,100 visible, 17 at or above $1,000 (avg $1,155.91). Expect `four_figure` to reach 0 and the stale row count to fall to 0.

### Price Association Fix (September 2026)
The price attached to an inferred sale is now the last history point **strictly before** the offer drop, at **any** distance. `merge_asof(direction='backward', allow_exact_matches=False)` in `keepa_deals/stable_calculations.py`.

`csv[1]` / `csv[2]` hold the **lowest** New / Used offer price, not any one copy's price, so when the cheapest copy sells the series steps **up** to the next cheapest listing at essentially the same timestamp. The previous `merge_asof(direction='nearest')` had no tie-break and recorded that asking price on **5 of 7 sales across 3 ASINs** measured live on 2026-09-11 ($124.85 stored as $1,000.00, $49.95 as $499.95, $328.19 as $625.59). 4 of those 7 had a price point on the exact minute of the drop, so `allow_exact_matches=False` does most of the work.

**No time threshold, by owner decision on measured data (2026-09-12).** A 240h tolerance was proposed and rejected: the real preceding-gaps were 3.0, 5.1, 10.2, 252.1, 389.6, 516.4 and 2281.4 hours, bimodal with nothing between 10h and 252h, so the threshold would have discarded 4 of 7 true sales. The series is a change-log, so a long gap means the lowest offer had not changed and the distant point is correct. A stale-price guard, if ever wanted, needs continuity of the series across the gap rather than gap length; that is an open item. Because 0 of 7 drops lacked a prior point, `Deal Trust` and xAI-rescue traffic were effectively unchanged by this fix. *(The rescue itself was removed on 2026-09-16 — see "xAI Sales Rescue Removed" above.)*

**Heavy path only, and it repairs nothing.** Only newly discovered deals are affected — the light path never recomputes `List_at` or `1yr_Avg`, and `recalculator.py` is API-free. Rows written under the old association keep their inflated values until a heavy re-fetch replaces them. Recovery is a separate, open decision.

### Dynamic ROI Calculation
ROI is not a database column. It is calculated dynamically (`(Profit / All_in_Cost) * 100`) on the frontend for display and in backend SQL queries for sorting. `All-in Cost` strictly equals `buy_cost_paid` + prep fee, and excludes Amazon fees to ensure this calculation remains accurate.

### Smart Ingestion & Token Rate Adaptation (August 2026 Update)
To resolve task livelocks under upgraded Keepa API plans (e.g. 25 tokens/min):
1. **5-Minute Ingestion Interval:** `smart-ingestor-run` in `celery_config.py` runs every **5 minutes** (`crontab(minute='*/5')`). This prevents 1-minute `TokenRechargeError` loops and giant log file bloat.
2. **Granular Burst Threshold:** `TokenManager.BURST_THRESHOLD` is capped at **50 tokens** for high refill rates (>= 20/min) and **40 tokens** for lower rates (< 20/min).
3. **Low-Cost Buffer Exit:** For low-cost API calls (cost <= 10), Recharge Mode exits as soon as tokens reach **20**, allowing background status and deal checks to proceed without waiting for full bucket refills.
