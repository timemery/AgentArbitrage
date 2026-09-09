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

### C-3. `Data_Logic.md` describes a `Deal Trust` fallback state — CORRECTED IN PRIORITY 1
> **Fallback Status**: If the deal uses the `avg365` fallback price … this field is set to
> **"Low (Est.)"**.

**Correction (see Priority 1): this state IS still reachable.** The `avg365` fallback was
removed from `stable_calculations.py` in March 2026, but a second one survives in
`new_analytics.py:83-107` (the `1yr. Avg.` path), and `processing.py:250` reads its
`price_source` flag and writes `"Low (Est.)"`. The doc is not describing a dead state.
The rest of this item stands: `/api/deals` filters `Deal_Trust` with
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

---
---

# PRIORITY 1 — INFERRED SALE PRICE

`INFERRED_PRICE_LOGIC.md` traced against `keepa_deals/stable_calculations.py` and
`keepa_deals/new_analytics.py`.

## Correction to Priority 0, C-3

P0 C-3 stated that the `Deal Trust = "Low (Est.)"` state can no longer occur. **That is wrong,
and the reason matters for this Priority.** The state is still reachable: `new_analytics.py:107`
sets `price_source = 'Keepa Stats Fallback'` from a *live* listing-average fallback inside
`get_1yr_avg_sale_price`, and `processing.py:250` reads that flag and writes
`row_data['Deal Trust'] = "Low (Est.)"`. What was removed in March 2026 was the fallback in
`stable_calculations.py` (the `List at` path). A second one survives in `new_analytics.py`
(the `1yr. Avg.` path) — see A-8 below. The rest of C-3 stands: `wsgi_handler.py:2212` casts
`"Low (Est.)"` to `0.0`, so any non-zero Deal Trust filter silently excludes those rows.

## Stage-by-stage trace

### Stage 1 — Inferring sale events (`infer_sale_events`, `stable_calculations.py:174`)

| Doc claim (`INFERRED_PRICE_LOGIC.md` §2) | Code | Match |
| --- | --- | --- |
| Correlate within a **240-hour** window | `:254` `search_window = timedelta(hours=240)` | ✅ |
| "over the last **two years**" | `:206` `timedelta(days=1095)` — **three years** | ❌ doc stale |
| Trigger = drop in New **or** Used offer count | `:213-232`, `csv[11]` and `csv[12]`, `.diff() < 0` | ✅ |
| Confirmation = drop in sales rank, `csv[3]` | `:250-252`, `df_rank['rank_diff'] < 0` | ✅ |
| Price via `pandas.merge_asof`, nearest listing price | `:305` `direction='nearest'` | ✅ |
| Sparse lookahead **30 days** (`Data_Logic.md` §3) | `:271` `timedelta(days=30)` | ✅ |

### Stage 1.5 — XAI Rescue (`xai_sales_inference.py`)

| Doc claim (§2.5) | Code | Match |
| --- | --- | --- |
| Fires on 0 confirmed sales **or** no offer drops | two call sites, `:236` and `:315` | ✅ |
| Skipped when rank > 2,000,000 | in `infer_sales_with_xai` | ✅ |
| Rescued sales "injected back into the pipeline as valid Inferred Sales" | `:243` and `:322` `return` **before** the IQR block at `:328-341` | ❌ — see A-9 |

### Stage 2 — Sanitisation (`stable_calculations.py:328-341`)

Symmetrical IQR exactly as documented: Q1/Q3 via `np.percentile`, bounds `Q1 − 1.5·IQR` and
`Q3 + 1.5·IQR`, inclusive filter. ✅ But note two undocumented consequences, both material:

* It runs **once, across the whole 3-year set, before any seasonal grouping**. A genuine
  off-season trough sale is a low outlier relative to peak-season sales, so it can be deleted
  before `Expected Trough Price` is computed from the trough month. The trough estimate is
  therefore derived from a set whose lowest prices have already been trimmed. Worked example 1
  below shows this happening.
* It is skipped entirely for XAI-rescued sales (A-9).

### Stage 3 — Price calculation (`analyze_sales_performance`, `stable_calculations.py:403`)

| Doc claim (§4A) | Code | Match |
| --- | --- | --- |
| Peak Month = highest **median** price | `:470` `monthly_stats['median'].idxmax()` | ✅ |
| Primary: **Mode** of peak month | `:493-495` `st.mode`, used when `count > 1` | ✅ |
| Fallback 1: **Median** if no distinct mode | `:497` | ✅ |
| Sparse Rescue when sales < **3** | `:415` `MIN_SALES_FOR_ANALYSIS = 3`, `:450` median | ✅ |
| Ceiling = 90% of `Min(AMZ current, 180d, 365d)` | `:504-519` | ✅ |
| Trough = **median** of trough month | `:482` | ✅ (but only on the ≥3-sale branch — A-11) |
| Hard ceiling: price > $1,500 rejected without AI | `:566` — applied to the **post-cap** price | ⚠️ order, see C-8 |
| 3× current-Used markup **forces** the AI check | `:581` | ✅ |
| Sparse / Fallback source **skips** the AI check | `:591` | ✅ |
| *(no doc claim)* | `:588` **`elif is_capped_by_ceiling: is_reasonable = True`** | ❌ undocumented third bypass — A-10 |

### 1-Year Average (`get_1yr_avg_sale_price`, `new_analytics.py:34`)

| Doc claim (§4B) | Code | Match |
| --- | --- | --- |
| Filter sane sales to last 365 days | `:63-64` | ✅ |
| **Mean** of those prices | `:67` `.mean()` | ✅ (the function's own docstring at `:36` says "median" — wrong) |
| Threshold: at least **1** sale | `:66` `if len(df_last_year) >= 1` | ✅ |
| Fallback: `stats.avg365` (**Used**) | `:83-104` builds five candidates and `:107` takes **`max`** | ❌ — A-8 |

---

## Worked example 1 — normal path, ≥3 sales

Six confirmed sale events (cents), all inside the 3-year window:

| Date | Price (cents) |
| --- | --- |
| 2025-08-14 | 4200 |
| 2025-08-27 | 5500 |
| 2025-09-02 | 5500 |
| 2026-01-11 | 2800 |
| 2026-08-19 | 5500 |
| 2026-08-30 | 6900 |

**Step 1 — IQR sanitisation** (`:328-341`). Sorted: 2800, 4200, 5500, 5500, 5500, 6900.

```
Q1 (25th pct, linear) = 4200 + 0.25 × (5500 − 4200) = 4525
Q3 (75th pct, linear) = 5500
IQR                   = 5500 − 4525          = 975
lower = 4525 − 1.5 × 975 = 3062.5
upper = 5500 + 1.5 × 975 = 6962.5
```

2800 < 3062.5 → **rejected**. 6900 ≤ 6962.5 → kept. `sane_sales` = 5 events.
**The January sale — the only winter data point, and the one a trough estimate depends on — is
gone before seasonality is ever considered.**

**Step 2 — seasonal grouping** (`:466-473`). Month 8: 4200, 5500, 5500, 6900 → median 5500.
Month 9: 5500 → median 5500.

```
monthly_stats['median'].idxmax() → tie at 5500 → pandas returns the FIRST index → month 8
monthly_stats['median'].idxmin() → tie at 5500 → pandas returns the FIRST index → month 8
peak_season_str = 'Aug'   trough_season_str = 'Aug'
```

Peak and trough collapse to the same month on a median tie. The code comments the single-month
case (`:471`, *"If only 1 month, peak and trough are the same"*) but does not guard the tie.
`Expected Trough Price` = median of month 8 = 5500 = **$55.00 — identical to the peak.**

**Step 3 — `List at`** (`:490-497`). `peak_season_prices = [4200, 5500, 5500, 6900]`.
`st.mode` → value 5500, count 2. `count > 1` → mode wins.
`peak_price_mode_cents = 5500` → `get_list_at_price` (`:648`) → **`List at = $55.00`**.

**Step 4 — Amazon ceiling** (`:504-527`). Say `stats.current[0] = 8900`, `avg180[0] = 9500`,
`avg365[0] = 9900`. `min = 8900`; `ceiling = 8900 × 0.90 = 8010`. `5500 ≤ 8010` → not capped.

**Step 5 — gates** (`:566-596`). `5500 ≤ 150000` → not absurd. `stats.current[2] = 2600`
($26.00 current Used) → `ratio = 5500 / 2600 = 2.12` ≤ 3.0 → not suspicious.
`price_source = 'Inferred Sales'`, not capped → falls to the `else` → **AI check runs.**
Matches the doc exactly.

**Step 6 — downstream.** From 2026-09-09, `one_year_ago = 2025-09-09`. Sane sales inside it:
5500 and 6900 (the 2026-01-11 event was the outlier that was removed).

```
1yr Avg      = (5500 + 6900) / 2 / 100                   = $62.00
Percent Down = ((62.00 − 26.00) / 62.00) × 100           = 58.06%
all_in_cost  = 26.00 + (26.00 × 0.15) + 2.50 + 2.00      = $34.40
fba_fee      = 550 / 100                                  = $5.50
referral     = 55.00 × 0.15                               = $8.25
AMZ fees     = 8.25 + 5.50                                = $13.75
Profit       = 55.00 − 34.40 − 13.75                      = $6.85
Margin       = 6.85 / 55.00 × 100                         = 12.45%
ROI          = 6.85 / 34.40 × 100                         = 19.91%
Min list at  = (34.40 + 5.50) / (1 − 0.10 − 0.15)         = $53.20
```

Note the shape of the result: **Min. List at ($53.20) is within $1.80 of Max. List at ($55.00).**
The whole deal rests on a $1.80 band, and the overlay does not show them adjacently in a way
that makes that visible — and per P0 A-3 it does not even show $55.00, it shows
`List_Price_Highest`.

## Worked example 2 — sparse rescue, 2 sales, forced AI check

Two confirmed events: 3000 and 9000 cents.

**IQR with n = 2** (`:330-334`):

```
Q1 = 3000 + 0.25 × 6000 = 4500
Q3 = 3000 + 0.75 × 6000 = 7500
IQR = 3000;  lower = 0;  upper = 12000
```

With two points the bounds always straddle both, so **IQR can never reject anything at n ≤ 3.**
Both survive.

`len(sane_sales) = 2 < MIN_SALES_FOR_ANALYSIS` → sparse branch (`:447-452`):

```
peak_price_mode_cents = median([3000, 9000]) = 6000  →  List at = $60.00
price_source          = 'Inferred Sales (Sparse)'
peak_season_str       = '-'      (never assigned on this branch)
trough_season_str     = '-'      (never assigned)
expected_trough_price = -1       (never computed)
```

Ceiling: assume no Amazon offer → `valid_amz_prices` empty → no cap.
Hard ceiling: `6000 ≤ 150000` → not absurd.
3× check: `stats.current[2] = 1800` ($18.00) → `ratio = 6000 / 1800 = 3.33 > 3.0` →
`is_suspiciously_high = True` → the sparse skip at `:591` is bypassed → **AI check runs.**

That is what the doc says should happen. **But the prompt it runs is degraded**: `season` is
passed as `peak_season_str`, which on this branch is the literal string `-`. The model is asked
*"is a peak selling price of $60.00 reasonable during -?"* (`:60` of the prompt template) with
`Identified Peak Season: "-"`. The seasonal context the doc calls "critical to prevent the AI
from falsely rejecting valid peak season prices" is absent in exactly the case flagged as most
in need of scrutiny. See A-12.

Downstream:

```
all_in_cost = 18.00 + (18.00 × 0.15) + 2.50 + 2.00 = $25.20
referral    = 60.00 × 0.15                          = $9.00
AMZ fees    = 9.00 + 5.50                           = $14.50
Profit      = 60.00 − 25.20 − 14.50                 = $20.30
Margin      = 20.30 / 60.00 × 100                   = 33.83%
ROI         = 20.30 / 25.20 × 100                   = 80.56%
```

**A median of exactly two sales, $30 and $90, produces an 80.6% ROI headline** and an
`Expected Trough Price` of nothing. The dashboard's Estimate Trust column carries the only hint,
and only if `total_offer_drops` was non-zero.

## Worked example 3 — the `1yr. Avg.` listing-average fallback

Four confirmed sales, all in 2024, none inside the last 365 days. `df_last_year` is empty
(`:64-66`), so `mean_price_cents` stays `-1` and the fallback at `:74-110` fires.

`stats.avg365` (cents):

| Index | Condition | Value |
| --- | --- | --- |
| 2 | Used | 3100 |
| 19 | Used - Like New | 8800 |
| 20 | Used - Very Good | 6400 |
| 21 | Used - Good | 4200 |
| 22 | Used - Acceptable | 2900 |

```
candidates = [3100, 8800, 6400, 4200, 2900]
:107  mean_price_cents = max(candidates) = 8800     # comment reads "Use the Max (Optimistic)"
1yr Avg = $88.00
```

The doc (§4B step 4) says the fallback is **`stats.avg365` (Used)** — index 2 — which is
**$31.00**. The code returns **$88.00**, 2.84× higher, by selecting the most expensive condition
tier available.

Effect on the discount signal, with `Price Now = $26.00`:

```
As coded (max):     ((88.00 − 26.00) / 88.00) × 100 = 70.45%
As documented (Used): ((31.00 − 26.00) / 31.00) × 100 = 16.13%
```

Same book, same moment. One reads as an extraordinary find, the other as ordinary. The Advisor
is handed the coded version verbatim — *"1-Year Average Price: $88.00, Percent Down from Avg:
70%"* (`ava_advisor.py:461-462`) — with no indication that no sale at $88.00 was ever observed.

These are **listing averages, not sale prices.** `AGENTS.md` §7.1 and `INFERRED_PRICE_LOGIC.md`
both state that fallbacks to listing averages are strictly prohibited, and the removed "Silver
Standard" used `min(avg90, avg365)` on the **Used** index only. This surviving fallback is
strictly more aggressive than the one that was deliberately deleted.

Partial mitigation: `price_source = 'Keepa Stats Fallback'` propagates to
`processing.py:250`, which overwrites `Deal Trust` with `"Low (Est.)"`, and
`wsgi_handler.py:2212` casts that string to `0.0` — so any non-zero Min. Deal Trust filter
(including Optimal Filters at 70%) excludes these rows. They are visible only with Deal Trust
set to "Any", where they show the inflated 70% discount and a blank-looking trust column.

---

## (A) CONFIRMED DEFECTS — Priority 1

### A-8. `1yr. Avg.` falls back to the **maximum** of five Keepa listing averages
**File:** `keepa_deals/new_analytics.py:83-107` — candidates built from `avg365` indices
2, 19, 20, 21, 22, then `mean_price_cents = max(candidates)` at `:107`.
**Input that breaks it:** any deal with zero inferred sales inside the last 365 days but
non-empty `stats.avg365`. Worked example 3: documented $31.00 becomes $88.00, and
`Percent Down` goes from 16% to 70%.
**Impact: highest in this Priority.** It is a listing average, not a sale price, which is the
exact failure mode `AGENTS.md` §7.1 and `INFERRED_PRICE_LOGIC.md` were written to prevent, and
`max()` is the most optimistic possible selection. It feeds `Percent Down`, the "Min. Below
Avg. (%)" filter, and the Advisor's headline discount. It does **not** feed `List at`, so
Profit and Margin are unaffected — that is the only thing keeping it out of the wrong-buy
category outright.

### A-9. XAI-rescued sale events bypass the IQR outlier rejection entirely
**File:** `keepa_deals/stable_calculations.py:243` and `:322` — both XAI branches `return`
before the sanitisation block at `:328-341`.
**Input that breaks it:** any deal where the algorithmic path finds zero confirmed sales or no
offer drops, so the rescue fires. Every price the model returns is accepted verbatim.
**Impact:** these are precisely the least-verified sale events in the system — inferred by an
LLM reading a history table rather than by the offer-drop/rank-drop correlation — and they are
the only ones exempted from the safety net the doc describes as protecting against "penny books
or repricer errors". A single hallucinated high price becomes the median in the sparse branch
(`:450`), and the sparse branch also skips the AI reasonableness check unless the 3× rule
happens to fire.

### A-10. A price capped by the Amazon ceiling skips the AI reasonableness check, undocumented
**File:** `keepa_deals/stable_calculations.py:588` — `elif is_capped_by_ceiling: is_reasonable = True`.
**Input that breaks it:** any computed `List at` above 90% of the lowest Amazon New price. The
branch sits **above** the sparse check at `:591`, so it also pre-empts the 3× forced check —
`is_suspiciously_high` is computed at `:576-583` and then never consulted on this path.
**Impact:** a wildly wrong computed price (bad history, one hallucinated XAI sale) that lands
above the Amazon ceiling is silently clamped to 90% of Amazon New and passed through with no
scrutiny at all. The clamp makes it *bounded*, not *right* — 90% of Amazon New on a book with no
real used demand is still a listing price no one will pay. Not mentioned anywhere in
`INFERRED_PRICE_LOGIC.md` §4A step 4, which lists only two skip conditions.

### A-11. `Expected Trough Price` and both season strings are never computed on the sparse branch
**File:** `keepa_deals/stable_calculations.py:447-452` — the sparse branch assigns only
`peak_price_mode_cents` and `price_source`. `peak_season_str` / `trough_season_str` keep their
`'-'` initialisers from `:419-420`; `expected_trough_price_cents` keeps `-1` from `:421`.
**Input that breaks it:** any deal with 1 or 2 inferred sales — the Sparse Sales Rescue case the
March 2026 policy specifically preserved.
**Impact:** the overlay's "Est. Buy Date" and "Est. Buy Price" (Group 4 of the Deal Details grid)
are blank for every sparse deal, and `Peak Season` is `-`. Compounds A-12.

### A-12. The seasonality classifier is always fed `'-'` for peak and trough month
**File:** `keepa_deals/processing.py:259-260`:
```python
peak_season_str  = row_data.get('Peak Sales Month',  '-')
trough_season_str = row_data.get('Trough Sales Month', '-')
```
The keys written upstream are **`Peak Season`** and **`Trough Season`** — `get_peak_season`
(`stable_calculations.py:643`) returns `{'Peak Season': ...}` and `headers.json` index 234 is
`Peak Season`. `'Peak Sales Month'` is not a key anywhere in the codebase, so both `.get()`
calls always hit the default.
**Input that breaks it:** every deal, on every heavy ingest.
**Impact:** `classify_seasonality` (`seasonality_classifier.py:103`) is called with
`peak_season_str = '-'` and `trough_season_str = '-'` for every book ever processed.
`Data_Logic.md` states the AI classifies "based on title, category, and **historical peak sales
months**" — the historical months are computed, stored, and then not delivered. The
`Detailed_Seasonality` value on every row is a title-and-category guess with the actual
observed seasonality withheld. `Detailed_Seasonality` drives the Season column, `Sells`
(Est. Sell Date), the Advisor prompt, and the Prime Picks "Year-Round Velocity Cap"
(`prime_picks_task.py`, rank > 2,000,000 rejection for non-seasonal items), so a
misclassification propagates into the Agent's Choice selection itself.
*Note the same class as PR #323: a display-name/DB-column key mismatch. This one is a
display-name/display-name mismatch and was not in that sweep.*

### A-13. `infer_sale_events` is re-run three or more times per product, with a non-deterministic branch
**File:** called at `stable_calculations.py:354` (`recent_inferred_sale_price`), `:637`
(`_get_analysis`), `:680` (`deal_trust`), and `new_analytics.py:54`
(`get_1yr_avg_sale_price`). Only `analyze_sales_performance` is memoised (`_analysis_cache`,
`:626-641`); `infer_sale_events` itself is not.
**Input that breaks it:** any deal that takes the XAI rescue path. Each call re-runs
`infer_sales_with_xai`, which is an LLM call — so `deal_trust` can compute its numerator from a
*different* set of rescued sales than the one `List at` was derived from.
**Impact:** the Estimate Trust percentage shown next to a price can describe a different sale
set than the price. It also multiplies the XAI sales-inference cost (measured at ~1,821 tokens
per call in the Sept 8 dev log) by 4 per rescued deal.

### A-14. `Deal Trust` can exceed 100%, and is `'-'` for the strongest rescue case
**File:** `keepa_deals/stable_calculations.py:678-685`.
`confidence = (len(sale_events) / total_offer_drops) * 100`, with no upper clamp.
**Input that breaks it:** the second XAI rescue branch (`:322`) returns rescued sales together
with the *real* `total_offer_drops_count`. If the model reports more sales than there were
offer drops — which is the entire premise of "hidden sales", stock depth > 1 — the ratio
exceeds 1.0 and Deal Trust renders as e.g. `240%`. The first rescue branch (`:243`) returns
`0` for the drop count, so `deal_trust` returns `'-'` (the divide-by-zero guard at `:681`
works), which then casts to `0.0` in `wsgi_handler.py:2212` and is excluded by every non-zero
Deal Trust filter.
**Impact:** the two XAI rescue paths produce opposite Deal Trust pathologies — one
above 100%, one hidden from the dashboard entirely.

### A-15. `NaN` from `merge_asof` survives the price guard and can void every sale event
**File:** `keepa_deals/stable_calculations.py:305-311`.
```python
price_at_sale_time = pd.merge_asof(...)['price_cents'].iloc[0]
if price_at_sale_time <= 0:   # NaN <= 0 is False → NaN is appended
    continue
```
**Input that breaks it:** any offer drop whose nearest price lookup yields `NaN` — an empty or
all-`NaT` price frame for that condition. The `NaN` enters `confirmed_sales`, then
`np.percentile` at `:330-331` returns `NaN`, so `lower_bound` and `upper_bound` are `NaN`, and
`lower <= x <= upper` is `False` for **every** element. `sane_sales` comes back empty and the
deal is rejected as having no inferred sales.
**Impact:** one bad price lookup silently discards a fully valid sale history. It is
indistinguishable in the logs from a genuine zero-sale deal.

### A-16. `merge_asof(direction='nearest')` has no tolerance
**File:** `keepa_deals/stable_calculations.py:305`.
**Input that breaks it:** a used-price history with a long gap — common on slow-moving books.
With no `tolerance=` argument, the nearest match can be months away from the offer drop, and
that price is recorded as the sale price. `INFERRED_PRICE_LOGIC.md` §2b describes this as
finding "the nearest listing price from the history at the **exact time** of the sale", which
implies a bound the code does not impose.
**Impact:** individual sale prices can be attributed from an unrelated market period. The IQR
step will catch an extreme case; a moderately wrong one passes.

### A-17. An empty xAI completion silently rejects the price
**File:** `keepa_deals/stable_calculations.py:91` — `is_reasonable = "yes" in content`.
**Input that breaks it:** any response whose visible content is empty or does not contain the
substring `yes`. The payload sets `"max_tokens": 10` (`:79`) against
`grok-4-fast-reasoning`, a reasoning model; if the budget is consumed before a visible token is
emitted, `content` is `''`, `is_reasonable` is `False`, and `peak_price_mode_cents` is set to
`-1` at `:600` — the deal loses its `List at` and is persisted as incomplete.
**Impact:** a transport-level condition is indistinguishable from a considered AI rejection.
Note the asymmetry: every *error* path fails open (`:33`, `:49`, `:104` all `return True`) but
this one fails closed. Frequency needs live logs — see B-9.

---

## (B) QUESTIONS FOR TIM — Priority 1

### B-6. Should the `1yr. Avg.` Keepa Stats fallback exist at all?
**Evidence it is deliberate:** `INFERRED_PRICE_LOGIC.md` §4B step 4 explicitly documents a
fallback to `stats.avg365`, and `processing.py:250` has purpose-built handling that downgrades
Deal Trust to `"Low (Est.)"` when it fires. Somebody built the whole warning path around it.
**Evidence it is a leftover:** `AGENTS.md` §2 forbids reintroducing "fallback pricing logic
that uses listing averages"; §7.1 says "If the primary data source is missing, REJECT the deal";
and the same document's own Critical Warning calls listing-average fallbacks "strictly
prohibited". The March 2026 removal appears to have covered only `stable_calculations.py`.
**Separable sub-question:** even if the fallback stays, is `max()` intended? The removed Silver
Standard used `min()` of two values on the Used index alone, specifically to be conservative.
`max()` of five condition tiers is the opposite choice, and the code comment
(`new_analytics.py:106`, *"Use the Max (Optimistic)"*) reads as intentional.

### B-7. Should the Amazon-ceiling cap be treated as a substitute for the AI check?
**Evidence it is deliberate:** the log line at `:589` says *"Price is capped by Amazon Ceiling
(Safe). Skipping AI Reasonableness Check"* — someone reasoned about this and called it safe,
and it does save an xAI call on a large fraction of deals.
**Evidence it is a hole:** it is not in the spec, it sits above the sparse and 3× logic so it
pre-empts the forced-check rule the doc calls out in bold, and "bounded by a competitor's price"
is not the same claim as "a used copy will sell for this".

### B-8. On a peak/trough median tie, should peak and trough be the same month?
**As built:** `idxmax()` and `idxmin()` both return the first matching index (worked example 1),
so `Expected Trough Price` equals the peak price and "Est. Buy Price" equals "Max. List at".
**Argument it is acceptable:** with sales concentrated in one month there genuinely is no
seasonal spread to report.
**Argument it is a problem:** the overlay presents "Est. Buy Price" as an actionable target.
Showing the peak price as the buy target inverts the advice. A guard (report `-` when
`peak_month == trough_month`) is a decision, not an obvious fix.

### B-9. How often does the reasonableness check return an empty completion?
Cannot be determined from code. `grep -c "XAI REJECTED" app.log` gives the rejection count, but
the log line at `:95` prints `content`, so an empty-string rejection is visible as
`AI responded ''`. Worth one grep before deciding whether A-17 is theoretical.

### B-10. Is the 3-year inference window intended, and should the doc move or the code?
`stable_calculations.py:206` uses 1095 days with the inline comment *"Extended to 3 years"*, and
`AGENTS.md` §7.7 justifies `dateRange: 4` as capturing "max 3-year history for AI analysis".
The code looks intentional and the doc looks stale — but `INFERRED_PRICE_LOGIC.md` §2a says
"two years" and `calculate_long_term_trend` hard-codes the string `"over 3 years"` (`:392`)
regardless of the actual span, so the label is wrong whenever history is shorter.

---

## (C) DOC/CODE DRIFT — Priority 1

### C-6. `INFERRED_PRICE_LOGIC.md` §4B documents a single-index fallback; the code takes a max of five
> **Fallback:** If 0 inferred sales are found, the system attempts to use **`stats.avg365`** (Used).

Code: `new_analytics.py:83-107`, five candidate indices, `max()`. **The doc appears correct
about intent** — a single Used-condition average is the conservative reading, and it is the only
one consistent with the same document's prohibition on optimistic fallbacks. This is A-8
stated as drift.

### C-7. `INFERRED_PRICE_LOGIC.md` §2.5 says rescued sales are "injected back into the pipeline"; they skip sanitisation
The doc's Stage 3 sanitisation is described as applying to the collected raw events. The XAI
returns at `:243` and `:322` are placed before it. **The doc appears correct**; the return
points are in the wrong place. This is A-9 stated as drift.

### C-8. The $1,500 hard ceiling is applied after the Amazon cap, not to the calculated price
> any calculated list price exceeding **$1,500** is automatically and immediately rejected
> without even querying the AI.

Code order (`:504-566`): Amazon ceiling clamp first, `> 150000` test second — so the test sees
the clamped value. A $4,000 computed price on a book with a $2,000 Amazon New price is clamped
to $1,800 and then rejected; the same $4,000 price on a book with a $1,000 Amazon price is
clamped to $900 and **passes**, with no AI check either (A-10). Which order is intended is a
judgement call, but the doc's word "calculated" reads as pre-clamp. Flagged, not resolved.

### C-9. `INFERRED_PRICE_LOGIC.md` §2a says "the last two years"; the code uses three
`:206`, `timedelta(days=1095)`. The code looks intentional (see B-10); the doc sentence is stale.

### C-10. `Data_Logic.md` says the seasonality AI is given "historical peak sales months"
It is given `'-'` (A-12). **The doc describes the intent and the code fails to deliver it.**

### C-11. Stale comments describing the removed Silver Standard as live
* `stable_calculations.py:413-414` — *"Fallback uses avg365 (Silver Standard) and SKIPS the XAI
  check"* — sits directly above `MIN_SALES_FOR_ANALYSIS = 3` and describes behaviour deleted in
  March 2026.
* `stable_calculations.py:591` — the skip condition still tests
  `price_source == 'Keepa Stats Fallback'`, a value `analyze_sales_performance` can no longer
  produce. Dead branch, harmless, but it makes the removal look incomplete to the next reader.
* `new_analytics.py:36` — the docstring says "Displays the **median** inferred sale price"; the
  code computes `.mean()` (`:67`), which is what the doc and the "Key Evolution" note both
  specify. Docstring is the wrong one.

### C-12. Two different Amazon-ceiling comparators exist
`stable_calculations.py:506-512` uses three prices (current, 180d, 365d), matching the doc.
`processing.py:483` uses four, adding `'Amazon - 90 days avg.'`. The second is inside the
lightweight clamp, which is gated off (`ENABLE_LIGHTWEIGHT_CEILING_CLAMP = False`), so it is
inert today — but it will not agree with the documented comparator when it is switched on.
