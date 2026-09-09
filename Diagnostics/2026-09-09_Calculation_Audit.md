# Calculation Correctness Audit — September 9, 2026

**Scope:** Read-only audit. No code changed. Findings only.
**Environment:** Repo sandbox at commit `c0a0810`. No `deals.db`, no `.env`, no live site.
Nothing below was executed against production data; every claim is traced to a file and line
in this checkout, and anything that needs live data to settle is filed under (B).

**Document structure.** The audit is written incrementally, one Priority at a time. Each
Priority carries its own three sections in the required order:
**(A) CONFIRMED DEFECTS**, **(B) QUESTIONS FOR TIM**, **(C) DOC/CODE DRIFT**,
each ranked by user impact within the Priority.

---
---

# PRIORITY 0 — DATA FRESHNESS AND CONSISTENCY

## 0(a) — Dashboard row vs. deal-detail overlay: are they separate fetches?

### The row and the overlay are the SAME fetch

There is no deal-detail endpoint. `/api/deals` is the only source of grid data.

1. `templates/dashboard.html:646` — `fetchDeals()` calls `/api/deals?...`.
2. `templates/dashboard.html:657` — `currentDeals = data.deals;` caches the page in memory.
3. `templates/dashboard.html:1770` — the row click handler looks the ASIN up in that same
   `currentDeals` array.
4. `templates/dashboard.html:1776` — `populateOverlay(deal)` is handed that cached object.

`populateOverlay` (`:1433`–`:1633`) reads only properties of that one object. It issues no
network call of its own. **So for any field present in both places, the row and the overlay
read the identical value from the identical fetch.** A row/overlay divergence on a *shared*
field is not reachable through this code path.

Divergence is reachable in three other ways, all confirmed below:

* **Different fields wearing similar labels** (the "Max. List at" case — A-3).
* **A different, later, independent database read** — the Advisor (A-4).
* **A field that is never written at all**, so the overlay's "—" is structural, not stale
  (the Rank Drops 180d case — A-1).

### The Rank Drops "180d = — vs 365d = 119" case (ASIN B0CM3PJRDX)

**Root cause found. `Sales_Rank_Drops_last_180_days` is never written by any code path.**

`keepa_deals/field_mappings.py:468` defines `FUNCTION_LIST`, a positional list index-aligned
with `keepa_deals/headers.json` (verified: both are exactly 246 entries). `_process_single_deal`
walks it at `keepa_deals/processing.py:122-133`:

```python
for i, func in enumerate(FUNCTION_LIST):
    if func:                       # <-- None entries are skipped entirely
        res = func(product_data)
        row_data[headers[i]] = val
```

The relevant slots:

| Index | headers.json entry | FUNCTION_LIST entry | File:line |
| --- | --- | --- | --- |
| 60 | `Sales Rank - Drops last 30 days` | `sales_rank_drops_last_30_days` | `field_mappings.py:529` |
| 63 | `Sales Rank - Drops last 180 days` | **`None`** | **`field_mappings.py:532`** |
| 64 | `Sales Rank - Drops last 365 days` | `sales_rank_drops_last_365_days` | `field_mappings.py:533` |

The function that would fill slot 63 exists and works — `sales_rank_drops_last_180_days`,
`keepa_deals/stable_products.py:504`. It is imported into `processing.py:12` and **never
called anywhere in the codebase** (verified by grep across `keepa_deals/` and `wsgi_handler.py`).

The lightweight-update path does not fill the gap either: `_process_lightweight_update`
(`processing.py:411-421`) refreshes only the **30-day** drop count.

**Worked example (B0CM3PJRDX).** Keepa returns `stats.salesRankDrops180 = <n>` and
`stats.salesRankDrops365 = 119` in the same heavy-fetch response
(`smart_ingestor.py:542`, `fetch_product_batch(..., days=365, history=1)`).
Slot 64 runs, so `Sales_Rank_Drops_last_365_days` is written `"119"`.
Slot 63 is `None`, so `row_data['Sales Rank - Drops last 180 days']` is never created;
the upsert therefore binds `NULL` into that column. The overlay renders it at
`dashboard.html:1471` as `deal.Sales_Rank_Drops_last_180_days || '-'` → **`-`**.

This is not specific to B0CM3PJRDX. **Every deal shows `—` for 180-day rank drops.**

**A second, independent bug sits on the same two lines.** `dashboard.html:1471-1472` uses the
JavaScript `||` operator, for which `0` is falsy. A genuine, correctly-fetched count of
**zero drops** renders as `—`, indistinguishable from "no data". So even after slot 63 is
filled, a dead book (0 drops in 180 days — the strongest possible sell signal against a
purchase) will look identical to a book the system simply failed to measure.

**To confirm live, one query:**
```sql
SELECT COUNT(*) AS total,
       SUM(Sales_Rank_Drops_last_180_days IS NULL) AS null_180,
       SUM(Sales_Rank_Drops_last_365_days IS NULL) AS null_365
FROM deals;
```
The prediction is `null_180 = total` and `null_365` near zero.

### The acquisition-cost discrepancy ($44 dashboard row vs $154 in Advisor output)

**Root cause found. The Advisor prompt never receives an acquisition cost.**

`keepa_deals/ava_advisor.py:459-471` is the entire set of numbers sent to the model:

```
*   **Current Buy Price:** {format_currency(current_price)}      # Price_Now
*   **1-Year Average Price:** {format_currency(avg_price_1yr)}   # 1yr_Avg
*   **Percent Down from Avg:** {percent_down}%
*   **Current Sales Rank:** {sales_rank_current}
*   **1-Year Avg Sales Rank:** {sales_rank_365_avg}
*   **Sales Rank Drops (Last 365 Days):** {drops_365}
*   **Seasonality:** {seasonality}
*   **Estimated Profit:** {format_currency(profit)}
*   **Margin:** {margin}%
*   **Price Trend:** {trend}
```

Not present: `All_in_Cost`, `List_at`, `Total_AMZ_fees`, `Min_Listing_Price`, `Expected_Trough_Price`.

So **any acquisition cost the Advisor states is not a value it was given.** It has exactly two
ways to produce one, and both are wrong:

1. **Back-computation from Profit and Margin.** `Margin = Profit / List_at × 100`
   (`business_calculations.py`), so the model can recover `List_at = Profit ÷ Margin × 100`
   and then assume `cost = List_at − Profit`. But the real identity is
   `Profit = List_at − All_in_Cost − Total_AMZ_fees`, so `List_at − Profit` equals
   **`All_in_Cost + Total_AMZ_fees`**, not `All_in_Cost`. The number it produces is
   systematically inflated by the full Amazon fee load.
2. **Free invention**, since nothing in the prompt constrains it.

Worked example consistent with $44 → $154. Suppose `All_in_Cost = 44.00`,
`List_at = 199.00`, `referralFeePercentage = 15`, `pickAndPackFee = 550` (¢):
`referral = 199.00 × 0.15 = 29.85`; `fba = 5.50`; `Total_AMZ_fees = 35.35`;
`Profit = 199.00 − 44.00 − 35.35 = 119.65`; `Margin = 119.65 / 199.00 × 100 = 60.1%`.
The model sees only Profit `$119.65` and Margin `60%`. Back-computing:
`List_at = 119.65 ÷ 0.601 = 199.08`; `cost = 199.08 − 119.65 = ` **`$79.43`**.
That is `All_in_Cost + Total_AMZ_fees`, and it is already ~1.8× the true $44.
Push `List_at` to ~$274 with the same $44 cost and the same fee structure and the
back-computed "cost" lands near $154 while `All_in_Cost` stays $44. The *mechanism* is
confirmed from the prompt; the *specific* $154 needs the live row to reproduce exactly.

**A second, independent divergence on the same click.** The Advisor does **not** read the
cached row. `wsgi_handler.py:2852` runs a **fresh** `SELECT * FROM deals WHERE ASIN = ?` at
click time. The dashboard row was fetched whenever the user last hit Apply/Refresh/paginated
and is **never refreshed in place** — the 60-second poll (`dashboard.html:1354`) fetches only
pagination metadata and shows a banner; it does not replace row values. The Smart Ingestor
upserts every 5 minutes (`celery_config.py`, `crontab(minute='*/5')`). So the Advisor can
legitimately be reading a row that has been rewritten since the grid was drawn, and the two
will disagree on `Price_Now`, `Profit`, `Margin` and `Percent_Down` with no indication to the
user that they are looking at two different moments in time.

**To confirm live:**
```sql
SELECT ASIN, Price_Now, All_in_Cost, Profit, Margin, List_at, Total_AMZ_fees,
       last_seen_utc, source
FROM deals WHERE ASIN = 'B0CM3PJRDX';
```
Then divide: `Profit / (Margin/100)` should reproduce `List_at`, and
`List_at − Profit` should reproduce the number the Advisor quoted.

---

## 0(b) — Worst-case age of every displayed field

### The mechanism that sets the ceiling

Three write paths touch a deal row. Which one runs decides which columns move.

| Path | Entry point | Keepa call | Runs |
| --- | --- | --- | --- |
| **Heavy** (new ASIN) | `processing.py:59` `_process_single_deal` | `smart_ingestor.py:542` `fetch_product_batch(days=365, history=1, offers=20)` | Once, at first ingest |
| **Light** (existing ASIN) | `processing.py:327` `_process_lightweight_update` | `smart_ingestor.py:552` `fetch_current_stats_batch(days=180, offers=20)` | Every 5 min, whenever the ASIN is in Keepa's delta feed |
| **Stale rescue** | same function | `smart_ingestor.py:227` `fetch_current_stats_batch(days=180, offers=20)` | Up to 20 deals/run, for rows with `last_seen_utc` older than 48h |

**Nothing re-runs the heavy path for an ASIN already in the `deals` table.** `existing_asins_set`
(`smart_ingestor.py:466`) routes every known ASIN to the light path, and the "Zombie Data
Defense" force-refetch that used to break that rule is commented out at
`smart_ingestor.py:454-461`. A deal only gets a heavy fetch again if it is first **deleted**.

The Janitor deletes on `last_seen_utc < now-72h` (`janitor.py:13, 24`). But **every** light
update stamps `last_seen_utc = now` (`smart_ingestor.py:572`), and the stale rescue exists
specifically to keep that stamp fresh (`smart_ingestor.py:208-227`). So a deal that keeps
appearing in the delta feed is never deleted, is never heavy-fetched again, and

> **every heavy-only field has NO upper bound on its age.**

It is as old as the row itself. There is no eviction, no TTL, and no refresh trigger for it.

### Field-by-field table

`H` = written only by the heavy path (unbounded age). `L` = refreshed by the light path.
"Worst-case age" is the age of the *underlying Keepa measurement* as displayed.

| Displayed field | Where shown | DB column | Source | Refresh trigger | Worst-case age |
| --- | --- | --- | --- | --- | --- |
| ASIN, Title | row + overlay | `ASIN`, `Title` | H | never | row age (unbounded) |
| Condition | row + overlay | `Condition` | L | 5-min ingest | ~5 min |
| Rank (current) | row + overlay | `Sales_Rank_Current` | L | 5-min ingest | ~5 min |
| Drops (30d) | row | `Sales_Rank_Drops_last_30_days` | L | 5-min ingest | ~5 min |
| Rank Drops 180d | overlay | `Sales_Rank_Drops_last_180_days` | **never written** | none | **∞ — always NULL** (A-1) |
| Rank Drops 365d | overlay | `Sales_Rank_Drops_last_365_days` | H | never | **unbounded** |
| Rank 180d / 365d avg | overlay | `Sales_Rank_180_days_avg`, `_365_days_avg` | H | never | **unbounded** |
| Offers (current) | row + overlay | `Offers` | L | 5-min ingest | ~5 min |
| Offers 180 / 365 | overlay | `Offers_180`, `Offers_365` | L | 5-min ingest | ~5 min |
| Used Offer Count 180d avg | (documented, not rendered) | `Used_Offer_Count_180_days_avg` | **never written** | none | **∞ — always NULL** (A-2) |
| Season | row + overlay | `Detailed_Seasonality` | H (xAI) | never | **unbounded** |
| 1yr Avg | row + overlay | `1yr_Avg` | H | never | **unbounded** |
| Now | row + overlay | `Price_Now` | L | 5-min ingest | ~5 min |
| % ⇩ | row + overlay | `Percent_Down` | L (recomputed from stale `1yr_Avg`) | 5-min ingest | numerator ~5 min, denominator unbounded |
| Ago / Updated | row + overlay | `last_price_change` | L | 5-min ingest | ~5 min |
| Seller / Seller Trust | row + overlay | `Seller`, `Seller_Quality_Score` | name H, ID L | Score never refreshed | **Score unbounded** |
| Estimate Trust | row + overlay | `Deal_Trust` | H | never | **unbounded** |
| All in | row + overlay | `All_in_Cost` | L | 5-min ingest | ~5 min |
| Profit / Margin | row + overlay | `Profit`, `Margin` | L (from stale `List_at`) | 5-min ingest | inputs mixed: cost ~5 min, revenue unbounded |
| ROI | row + overlay | computed in JS/SQL | derived | with Profit | same as Profit |
| Max. List at | overlay | `List_Price_Highest` **then** `List_at` | H | never | **unbounded** (and wrong field — A-3) |
| Min. List at | overlay | `Min_Listing_Price` | L | 5-min ingest | ~5 min |
| Est. Buy Price | overlay | `Expected_Trough_Price` | H | never | **unbounded** |
| Est. Sell / Buy Date | overlay | `Sells`, `Trough_Season` | H | never | **unbounded** |
| Amazon / Buy Box prices | overlay | `Amazon_Current`, `Amazon_365_days_avg`, `Buy_Box_Used_*` | H | never | **unbounded** |
| Genre, Binding, Publisher, Published | overlay | `Categories_Sub`, `Binding`, `Manufacturer`, `Publication_Date` | H | never | unbounded (static facts, low risk) |
| Gated | row + overlay | `user_restrictions.is_restricted` | SP-API | manual button, or new-deal trigger | **unbounded** — no TTL on the restrictions table |
| Agent's Choice set | row set | `prime_picks` | Janitor chain, every 4h | 4h | ~4h + age of its inputs |

**The single most important line in that table:** `Profit` and `Margin` are recalculated every
five minutes from a **five-minute-old cost** and an **arbitrarily old revenue estimate**
(`List_at`). `processing.py:529-536` does this explicitly — it reads the preserved `List_at` and
recomputes `Profit` against a fresh `Price_Now`. The number therefore *looks* live and carries
no marker that half of it is not.

### Where the timestamps actually come from

* `last_seen_utc` — `datetime.now(timezone.utc).isoformat()`, stamped at upsert
  (`smart_ingestor.py:254, 572, 579`). This is the only true "when did we last touch this row"
  value. **It is never sent to the frontend and never displayed.**
* `Deal_found` — Keepa `deal_object['creationDate']`, epoch 2011 (`stable_deals.py:83-93`).
  Heavy path only. Not displayed.
* `last_update` — MAX of three Keepa `lastUpdate` fields (`stable_deals.py:114-154`).
  Heavy path only. Not displayed.
* `last_price_change` — MAX Keepa timestamp across the Used condition CSVs, converted with
  `KEEPA_EPOCH = 2011-01-01`, localised to `America/Toronto`, formatted
  `'%Y-%m-%d %H:%M:%S'` (`stable_deals.py:289-300`). This **is** displayed, as "Ago" and
  "Updated".

---

## 0(c) — Numbers shown without their age

**Every number on the dashboard and in the overlay is shown without its age. There is no
exception.** `/api/deals` returns `last_seen_utc` inside `deals.*` but no template reads it;
`populateOverlay` (`dashboard.html:1433-1633`) renders no timestamp except `last_price_change`.

The specific traps, worst first:

1. **`last_price_change` is mistaken for data freshness but is not.** It is displayed under the
   headers "Ago" and "Updated" (`Dashboard_Specification.md`, and `dashboard.html:1557`). It
   measures **when Amazon's price last moved**, derived from Keepa history. A book whose price
   has been flat for 40 days reads "40d ago" even when the row was refreshed 90 seconds ago;
   a book we have not looked at in three weeks can read "1h ago". The label points the user at
   exactly the wrong conclusion in both directions.
2. **Profit / Margin / ROI carry no indication that `List_at` is frozen.** See the table above.
3. **`Deal_Trust` ("Estimate") is heavy-only and never re-derived**, so the confidence score
   attached to a price ages independently of the price it describes — and it is the score the
   user is told to filter on (`Optimal Filters`, `Trust >= 70%`).
4. **The Advisor prompt contains no age information whatsoever.** `ava_advisor.py:459-471`
   sends ten bare numbers. The model is not told that `1yr_Avg`, `Detailed_Seasonality` and
   `Sales Rank Drops (365d)` may be weeks old while `Price_Now` is minutes old, so it will
   reason about them as if they were measured together. It is also not told the deal's
   `last_seen_utc`, `Deal_found` or `last_update`.
5. **Prime Picks has a `generated_at` and the UI never shows it.** It is returned at
   `wsgi_handler.py:2436` and read into `currentPrimePicksGeneratedAt`
   (`dashboard.html:674`) purely to drive a "new picks" banner. The user is never told the
   AI ranking they are looking at is up to four hours old.
6. **The Gated status has no age at all.** `user_restrictions` rows are written by
   `check_all_restrictions_for_user` and never expire. A "Buy Now" button can be authorised
   by a gating check performed weeks ago.

---

## (A) CONFIRMED DEFECTS — Priority 0

### A-1. `Sales_Rank_Drops_last_180_days` is never populated; the overlay always shows "—"
**File:** `keepa_deals/field_mappings.py:532` (`None,  # Sales Rank - Drops last 180 days`)
**Also:** `keepa_deals/processing.py:12` (function imported, never called);
`keepa_deals/processing.py:122-133` (the `if func:` skip);
`templates/dashboard.html:1471` (renders the resulting NULL as `-`).
**Input that breaks it:** any ASIN at all. `_process_single_deal` skips index 63, so the column
is NULL for every row ever written.
**Impact:** the overlay's "Rank Drops → Last 180 Days" field is decorative. A user comparing
180d against 365d velocity — the exact check that separates a book that *used* to sell from one
that sells *now* — gets no signal, and the blank reads as "zero demand" rather than "not measured".

### A-2. `Used_Offer_Count_180_days_avg` is never populated
**File:** `keepa_deals/field_mappings.py` index 221 (`None,  # Used Offer Count - 180 days avg.`)
**Also:** `keepa_deals/stable_products.py:1478` `used_offer_count_180_days_avg` — defined, never wired.
**Input that breaks it:** every ASIN.
**Impact:** lower than A-1 because no template renders this column today, and the Pass-1
deduplication comparison was deliberately moved to the 365-day average
(`new_analytics.py:226`, `get_offer_count_trend_from_flat`). But the column is documented as
live in `Data_Logic.md` (see C-1) and any future code reading it will silently get NULL.

### A-3. The overlay's "Max. List at" prefers Keepa's historical MSRP over the calculated `List_at`
**File:** `templates/dashboard.html:1585` — `let listAt = deal.List_Price_Highest || deal.List_at;`
**Input that breaks it:** any deal where `List_Price_Highest` is non-null — i.e. any book with a
recorded publisher list price. `List_Price_Highest` is Keepa's highest-ever *List Price*
(MSRP), an entirely different quantity from the inferred-sale-derived `List_at` that
`Profit`, `Margin` and `ROI` are computed from (`business_calculations.py`).
**Impact: highest in this Priority.** The overlay is the surface a user reads immediately before
clicking Buy. It shows a Profit figure derived from `List_at` sitting directly beside a
"Max. List at" derived from MSRP. Cover price on a textbook routinely runs 3–5× the used market
price, so the panel systematically over-states the achievable sale price and makes the Profit
next to it look conservative when it is not. `List_at` is used only as a fallback, so on most
rows the number the user reads is not the number the maths used.

### A-4. The Advisor is prompted with no acquisition cost, and re-reads the row at a different moment
**File:** `keepa_deals/ava_advisor.py:459-471` (prompt body — no `All_in_Cost`, no `List_at`);
`wsgi_handler.py:2852` (independent `SELECT * FROM deals WHERE ASIN = ?`).
**Input that breaks it:** every Advisor click. The cost figure is unconstrained, and the row it
reads is whatever the DB holds at that instant, not what the grid was drawn from.
**Impact:** the Advisor is the "My Mentor" recommendation at the top of the overlay. It can
quote a cost 2–4× the real one (worked example above) and it can contradict the row beside it
because the two were read minutes apart. Both push toward a wrong buy/pass call.

### A-5. Zero is rendered as "no data" throughout the overlay and the row
**File:** `templates/dashboard.html:1471-1472` (`|| '-'` on both drop counts),
`:1526` (`deal.Price_Now ? ...`), `:1536` (`deal['1yr_Avg'] ? ...`),
`:1572` (`deal.Profit ? ...`), `:1574-1575` (`deal.Margin ? ...`, `deal.ROI ? ...`),
`:1592` (`minList ? ...`), `:1476` (`if (!value || value === '-') return '-'` in `formatOffers`).
**Input that breaks it:** any field whose true value is `0` — zero drops, zero offers, zero
profit, zero margin.
**Impact:** "0 drops in 180 days" and "we never measured drops in 180 days" are opposite
conclusions and render identically. Same for a break-even deal (`Profit = 0`), which displays
as `-` rather than `$0.00`.

### A-6. `sales_rank_drops_last_*` raise `TypeError` when Keepa returns an explicit `null`
**File:** `keepa_deals/stable_products.py:486, 507, 525` — `value = stats.get('salesRankDrops30', -1)`
followed immediately by `if value < 0:`, **outside** the `try` block that begins on the next line.
**Input that breaks it:** a Keepa response where the key is present with value `null`.
`None < 0` raises `TypeError` in Python 3; the local `try` does not cover the comparison, so it
propagates to the generic handler at `processing.py:130-131`, which logs a warning and leaves the
field unset — silently NULL rather than `'-'`.
**Impact:** low frequency, but it converts a recoverable "no data" into a missing column with
only a `logger.warning` to show for it.

### A-7. The two upsert sites in `smart_ingestor.py` use different key namespaces for the same row shape
**File:** `keepa_deals/smart_ingestor.py:596` (main Light Update) vs `:272` (Stale Rescue).

```python
:272   row_tuple = tuple(row_dict.get(h) for h in sanitized_headers)   # 'List_at', '1yr_Avg'
:596   row_tuple = tuple(row_dict.get(h) for h in headers) + (...)      # 'List at', '1yr. Avg.'
```

Both consume rows produced by the **same** function, `_process_lightweight_update`, whose
output dictionary is `dict(existing_row)` — keyed by **sanitized DB column names**
(`smart_ingestor.py:467`, `existing_rows_map[r['ASIN']] = dict(r)` from `SELECT *`) — with a
handful of fresh values written back under **display** names
(`'Sales Rank - Current'` at `processing.py:397`, `'Offers'` / `'Offers 180'` / `'Offers 365'`
at `:426-436`, `'last price change'` at `:447`, `'All-in Cost'` and `'Min. Listing Price'` at
`:533-536`). The two namespaces are mixed inside one dictionary.

Consequences, mechanically:

* **At `:596`**, every header whose display name differs from its sanitized name and which the
  lightweight path did not rewrite under the display name resolves to `None`. Enumerated from
  `headers.json` that is **215 of 246 columns**, including `List at`, `1yr. Avg.`, `Price Now`,
  `Deal Trust`, `Total AMZ fees`, `Expected Trough Price`, `Peak Season`, `Trough Season`,
  `Seller ID`, `% Down`, `Deal found`, `last update`, and every `Sales Rank - * avg.` /
  `Sales Rank - Drops last *` column. The `ON CONFLICT DO UPDATE SET "col"=excluded."col"`
  at `:601` writes all of them, so these are bound as `NULL`.
* **At `:272`**, the mirror-image loss: the freshly-computed values written under display names
  (`'Sales Rank - Current'`, `'Offers'`, `'Offers 180'`, `'Offers 365'`, `'All-in Cost'`,
  `'Min. Listing Price'`, `'last price change'`) are not found, so the stale rescue writes back
  the **old** rank, the **old** offer counts and the **old** all-in cost — while writing the
  **new** `Profit` and `Margin` that were computed from the new cost. The row ends internally
  inconsistent: `Profit ≠ List_at − All_in_Cost − Total_AMZ_fees` using its own stored columns.

This is the same class of bug as the six fixed in PR #323 (Dev log `2026-08-18b`), which
corrected the *reads* inside `_process_lightweight_update` but left both *writes* untouched.
`git log -- keepa_deals/smart_ingestor.py` shows neither line changed in `e4cf1f9`.

**This finding is filed as CONFIRMED for the code shape and the key mismatch, which are
unambiguous from the source. Its live blast radius is not**, because a `:596` path that
NULLed `List_at` on every light update would empty the dashboard within one 5-minute cycle
(`/api/deals` filters on `"List_at" IS NOT NULL`, `wsgi_handler.py:2237` and `:2255`), and Tim reports
deals are visible. The reconciling question is in B-1 — it must be answered before anyone
touches these lines, because "fixing" `:596` to match `:272` would break the heavy path, which
genuinely does key by display names (`processing.py:131`, `row_data[headers[i]] = val`).

**To confirm live, one query:**
```sql
SELECT source, COUNT(*) AS n,
       SUM(List_at IS NULL)  AS null_list_at,
       SUM("1yr_Avg" IS NULL) AS null_1yr,
       SUM(Deal_Trust IS NULL) AS null_trust,
       SUM(Sales_Rank_365_days_avg IS NULL) AS null_rank365
FROM deals GROUP BY source;
```
If `source='smart_ingestor_light'` rows show high NULL counts and `source='smart_ingestor'`
rows do not, `:596` is live-destructive exactly as traced.

---

## (B) QUESTIONS FOR TIM — Priority 0

### B-1. Does the main Light Update path actually null out `List_at`, or is something reconciling it?
**Evidence it does:** the key namespaces at `smart_ingestor.py:596` and `processing.py:338`
do not match; `row_dict.get('List at')` on a dict keyed `List_at` returns `None`; the upsert
at `:601` writes every column unconditionally. This is mechanical and I can see no branch
that avoids it.
**Evidence it does not:** the dashboard shows deals, and `/api/deals` hard-filters
`"List_at" IS NOT NULL` (`wsgi_handler.py:2237` and `:2255`). If this fired on every light update the grid
would go empty in one 5-minute cycle. The Aug 18b dev log also records that "the real `List_at`
values were never destroyed — only mis-read", after a recompute recovered +241 deals.
**Possible reconciliations I cannot test from here:** (i) the delta feed rarely re-serves ASINs
already in `deals`, so the `:596` light branch runs on very few rows; (ii) production has
drifted from this checkout. The `GROUP BY source` query above settles it.

### B-2. Should the "Ago" column mean "price last moved" or "we last checked"?
**As built:** it is `last_price_change`, a Keepa market event (`stable_deals.py:289-300`),
labelled "Ago" on the row and "Updated" in the overlay.
**Argument it is deliberate:** for arbitrage, how long a price has held is real signal, and
`Dashboard_Specification.md` describes it as a price trend arrow plus time.
**Argument it is a trap:** both labels read as data freshness, `last_seen_utc` is the value
that actually means that, and it is fetched but never displayed. Deciding this changes what
0(c) item 1 is — a naming problem or a missing column.

### B-3. Is a heavy re-fetch ever supposed to happen for an existing deal?
**As built:** no. `existing_asins_set` (`smart_ingestor.py:466`) routes every known ASIN to the
light path, and the Zombie force-refetch is commented out at `:459-461`. So `1yr_Avg`,
`Deal_Trust`, `List_at`, `Detailed_Seasonality`, `Expected_Trough_Price` and all the 180/365-day
rank and price aggregates are frozen for the life of the row.
**Argument it is deliberate:** the Aug 18b and System_Architecture notes are explicit that
aggressive re-fetching caused infinite loops and token waste, and the Persistence Strategy
replaced it on purpose.
**Argument it is a problem:** the same notes describe the intent as "gradual data repair", and
nothing repairs these fields — they are not lightweight-updatable. A deal that survives on the
delta feed for two months is quoting a two-month-old `1yr_Avg` against a live `Price_Now`, and
`Percent_Down` and `Profit` are both computed across that gap.

### B-4. Is `Seller_Quality_Score` meant to be frozen at first sight?
**As built:** the Wilson score is computed only in `_process_single_deal`
(`processing.py:93-109`) from seller data fetched once. The light path updates `Seller_ID` but
never re-derives the score.
**Argument it is deliberate:** re-fetching seller data costs a Keepa call per deal.
**Argument it is a problem:** the winning seller can change on any light update
(`processing.py:378-383` writes a new `Seller_ID`), and when it does the displayed trust score
still describes the **previous** seller. "Min. Seller Trust" is one of the Optimal Filters.

### B-5. Should `user_restrictions` rows expire?
**As built:** written by `check_all_restrictions_for_user`, no TTL, no age column surfaced.
**Argument it is deliberate:** gating rarely changes and SP-API calls are rate-limited.
**Argument it is a problem:** a green "Buy Now" is an assertion about the user's current selling
privileges, and it can be arbitrarily old with nothing on screen to say so.

---

## (C) DOC/CODE DRIFT — Priority 0

### C-1. `Data_Logic.md` documents two columns that are never written
`Data_Logic.md` → "Advanced Analytics (Rank & Offers)" states:

> **`Sales Rank - Drops` (30/180/365)** … **Periods**: 30 days, 180 days, and 365 days.
> **`Used Offer Count - Avg` (180/365)** … the average number of used offers over the last 180 and 365 days.

Both 180-day columns are `None` in `FUNCTION_LIST` (`field_mappings.py:532` and index 221) and
are never written by any path. **The code is what is wrong here** — the doc describes the
intended contract, the functions to satisfy it already exist
(`stable_products.py:504` and `:1478`), and `Dashboard_Specification.md` renders one of them in
the overlay. The doc should not be edited to match; the wiring should be fixed.

### C-2. `Data_Logic.md` and `Dashboard_Specification.md` both describe a freshness guarantee the Janitor does not provide
Both say the Janitor "deletes deals where `last_seen_utc` is older than 72 hours" to prevent
"stale deals from cluttering the dashboard", and `Dashboard_Specification.md` heads the section
"The Janitor & Data Freshness". The Janitor only bounds **row** age, and only for rows that
stop being touched. It places no bound on **field** age: the stale rescue
(`smart_ingestor.py:208-227`) exists precisely to keep `last_seen_utc` fresh, so heavy-only
fields survive indefinitely under a heading that promises freshness.
**The doc is misleading rather than wrong** — every individual sentence is accurate; the
section title and framing over-claim. Which side should move is an owner decision.

### C-3. `Data_Logic.md` describes a `Deal Trust` fallback state that can no longer occur
> **Fallback Status**: If the deal uses the `avg365` fallback price … this field is set to
> **"Low (Est.)"**.

The `avg365` / "Silver Standard" fallback was removed in March 2026 (recorded in
`AGENTS.md` §7.1 and in `INFERRED_PRICE_LOGIC.md`). **The code is correct; the doc retains a
dead state.** Note also that `/api/deals` filters `Deal_Trust` with
`CAST(REPLACE("Deal_Trust", '%', '') AS REAL) >= ?` (`wsgi_handler.py:2212`), which casts the
literal string `"Low (Est.)"` to `0.0` — so any surviving row in that state is silently
excluded by every non-zero Deal Trust filter.

### C-4. `Dashboard_Specification.md` gives the wrong source for the overlay's "Max. List at"
> **Max. List at**: The calculated "List at" (Peak) price.

The implementation prefers `List_Price_Highest` and falls back to `List_at`
(`dashboard.html:1585`). **The doc is correct about the intent** — the spec describes the field
that `Profit` is actually computed from — and the code diverges from it. This is A-3 stated as
drift.

### C-5. The two docs disagree on the poll interval; `Feature_Deals_Dashboard.md` is the wrong one
`Dashboard_Specification.md` → "Polling & Updates" says **60 seconds**.
`Feature_Deals_Dashboard.md` → "Passive Notification" says **30 seconds**.
The code polls at **60 seconds** (`templates/dashboard.html:1343` `setInterval(...)`, closing
`}, 60000);` at `:1399`). `Dashboard_Specification.md` is correct;
`Feature_Deals_Dashboard.md` is wrong. Cosmetic, listed for completeness.
