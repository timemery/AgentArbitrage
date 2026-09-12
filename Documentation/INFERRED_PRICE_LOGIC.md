# Technical Documentation: Inferred Price Calculation Logic

## 1. Overview

This document details the system used to calculate the **List at** (Peak), **Trough**, and **1-Year Average** prices for a given product (ASIN). The entire system is predicated on the concept of an "inferred sale," which is a historical moment where data strongly suggests a transaction occurred.

The primary logic is housed in:
- `keepa_deals/stable_calculations.py`
- `keepa_deals/new_analytics.py`

The process follows three main stages:
1.  **Inferring Sale Events** (Finding the data points).
2.  **Sanitization** (Removing noise).
3.  **Calculation & AI Validation** (Determining the final prices).

------

## ⚠️ Critical Warning: The Dangers of Fallback Data

**Do NOT attempt to "fill in the blanks" with unverified data.**

A critical lesson learned in January 2026 is that fallback mechanisms—attempts to provide a price when the primary logic finds none—are extremely dangerous. They often result in the system confidently presenting garbage data, which then triggers downstream rejections (like the AI Reasonableness Check) or, worse, leads users to make bad buying decisions.

**Specific Failure Case: The "High Velocity" Fallback (Deprecated)**
The system previously contained an *unsafe* fallback logic:
> *If no sales are inferred, but `monthlySold > 20`, use the `Used - 90 days avg` price.*
This caused massive deal rejection rates because it often grabbed stale, high-priced Used listings for books that only sold as New. This logic has been **REMOVED**.

**The "Safe Fallback" Compromise and Subsequent Removal (Mar 2026)**
To address data sparsity without sacrificing safety, we briefly introduced a **Validated Fallback** (the "Silver Standard"). It attempted to use the **Minimum** of `stats.avg90` and `stats.avg365` for **Standard Used** conditions only when inferred sales < 3.

**REMOVAL REASONING:**
The user subsequently observed that this fallback logic—while safely preventing astronomical profits via `min()`—still essentially relied on *listing prices* rather than *true inferred sale prices*. This tactic, originally designed to increase the volume of deals found, compromised the core promise of only providing "true deals."

**The Surviving Fallback and Its Removal (Sep 2026)**
The March 2026 removal covered `stable_calculations.py` (the `List at` path) only. A
second fallback survived in `new_analytics.py` (the `1yr. Avg.` path) and went on
firing for another six months. It was **strictly more aggressive** than the one that
had been deliberately deleted: where the Silver Standard took `min(avg90, avg365)` on
the **Used** index alone, this one built candidates from five `avg365` condition tiers
(Used, Like New, Very Good, Good, Acceptable) and took the **`max`**. On the audit's
worked example a true $31.00 became $88.00, turning a 16% discount into a reported
70% one, and that number was handed verbatim to the Advisor and to Prime Picks Pass 1.

It was removed on **2026-09-11** by owner decision (audit item B-6). Zero inferred
sales inside the last 365 days now returns `None`.

**Current Principle:** Fallbacks to listing averages are **strictly prohibited**, on
**every** price path. We ONLY rely on inferred sale prices (derived from offer drops
correlating with rank drops) to calculate profits. Sparse inferred sales (1-2 events)
are still permitted as they represent true historical sales, but Keepa stats averages
are not.
**Hard Ceiling Safety:** To prevent astronomical fake profits (e.g., a $4,000 "List At" price), any calculated list price exceeding **$1,500** is automatically and immediately rejected without even querying the AI.

------

## 2. Stage 1: Inferring Sale Events

This is the foundational step handled by `infer_sale_events(product)` in `keepa_deals/stable_calculations.py`.

### a. The "Sale" Trigger and Confirmation
A sale is inferred by correlating two distinct events within a **240-hour** (10-day) window over the last two years:

1.  **The Trigger:** A drop in the offer count for either **New** or **Used** listings.
    -   Source: `csv[11]` (New Count) and `csv[12]` (Used Count).
    -   Mechanism: `diff()` detects negative changes.
2.  **The Confirmation:** A drop in the product's **Sales Rank** (`csv[3]`).
    -   Rationale: A rank drop indicates Amazon registered a sale.
    -   Window: If a rank drop occurs within 240 hours *after* an offer count drop, it is flagged as a confirmed sale.

### b. Price Association

When a sale is confirmed, the system attaches a price to it from the matching price
series — `csv[1]` for a New offer drop, `csv[2]` for a Used one.

**It takes the last price point STRICTLY BEFORE the offer drop**, via
`pandas.merge_asof(direction='backward', allow_exact_matches=False, tolerance=...)`.

**Why "before" and not "nearest".** `csv[1]` and `csv[2]` hold the **lowest** New /
Used offer price, not the price of any particular copy. When the cheapest copy
sells, the series does not record what it sold for — it steps **up** to whatever the
next cheapest listing asks, at essentially the same timestamp as the offer-count
drop that marks the sale. The price in force immediately *before* the drop is
therefore the best available estimate of what the copy sold at, and the point *at or
after* it is the asking price of a copy that did **not** sell.

Until September 2026 this was `merge_asof(direction='nearest')` with no tolerance and
no tie-break, so it could land on the at-or-after point and store that asking price.
Because Keepa stamps the offer-count drop and the price step-up at the same minute, a
zero-distance match was the common case rather than the edge — which is why
`allow_exact_matches=False` matters as much as the direction does. Confirmed live on
**5 of 7 sales across 3 ASINs** on 2026-09-11: **$124.85 recorded as $1,000.00**,
**$49.95 as $499.95**, **$328.19 as $625.59**. The round numbers are the tell — those
are prices a seller typed into a listing, not prices anything transacted at. See
`Dev_Logs/2026-09-11b_Remove_1yr_Avg_Listing_Average_Fallback.md` §4b for the
evidence.

### b.1 The time tolerance

`PRICE_ASSOCIATION_TOLERANCE_HOURS` in `keepa_deals/stable_calculations.py` is
**240 hours (10 days)**. If the last price point before an offer drop is older than
that, **no price is attached and the sale is discarded** — it is never priced from a
distant point.

*   **Why a tolerance exists.** The price series is a change-log, so in principle a
    value persists until the next point and any age is "current". In practice a
    months-old point can predate a stretch with no offers at all. The live
    diagnostic found exactly that on ASIN `1468308963`, where the nearest price
    point was **60.3 days** from the drop.
*   **Why 240.** Measured across every Keepa `csv` fixture in `tests/`, the gap
    between an offer drop and the price point preceding it is **1h (×17), 6h (×15)
    and 24h (×2)** — so 24 hours is a hard floor (the 24h pair is
    `tests/test_synchronous_updates.py`) and the fixtures put **no ceiling on it at
    all**, their values being the generators' grid step rather than a property of
    Keepa data. 240 hours is ten times that floor, matches the magnitude of the
    240-hour rank-confirmation window the system already treats as "the same event",
    and is six times smaller than the one measured bad gap. It is a **named
    module-level constant**, deliberately not read from the confirmation window:
    these are two different judgements and must be tunable apart.
*   **Which way it errs.** Lowering it discards more true sales on books whose price
    simply has not changed in a while. That shows up as fewer inferred sales, a
    lower `Deal Trust` and more NULL prices — **never as a wrong price**, which is
    the direction the Critical Warning above requires.
*   **The offer drop still counts.** A drop whose price cannot be associated stays
    in the `Deal Trust` denominator, so the score reflects the loss.
*   **NaN safety.** `merge_asof` returns `NaN` when the tolerance matches nothing,
    and `NaN <= 0` is `False`, so the pre-existing `price <= 0` guard cannot catch
    it on its own. There is an explicit `pd.isna` check ahead of it; without one a
    `NaN` would poison the IQR bounds, the mean and the mode for the whole ASIN.

> **This changes newly computed prices only.** A fix to the inference repairs no
> existing row: the light path never recomputes `List_at` or `1yr_Avg`, and
> `recalculator.py` is API-free and cannot rebuild either. Rows written under the
> old association keep their inflated values until a heavy re-fetch replaces them.
> Recovery is a separate decision. `diagnose_inferred_sales.py` reports, for each
> sale, both what today's code records and what the pre-fix nearest-match would have
> recorded, so a stored number can still be accounted for.

------

## 2.5 Stage 1.5: XAI Rescue Mechanism ("Hidden Sales")

**Introduced:** Feb 2026 (`xai_sales_inference.py`)

If the algorithmic approach (Stage 1) finds **0 confirmed sales** or detects **no offer drops** (which is mathematically impossible for a sold item unless stock depth > 1), the system triggers a "Rescue" attempt.

1.  **Context Assembly:** The system constructs a markdown table representing ~365 days of history, aligning Rank, Price, and Offer Count time-series data.
2.  **AI Analysis:** This table is sent to **xAI (Grok)** with a specific prompt to identify "Hidden Sales"—instances where Sales Rank improved (dropped) significantly without a corresponding drop in Offer Count (implying the seller had multiple units).
3.  **Integration:** Sales identified by the AI are injected back into the pipeline as valid "Inferred Sales," allowing the deal to proceed to analysis instead of being rejected.
4.  **Safety:** To preserve tokens, this rescue is skipped if the item's current Sales Rank is > 2,000,000 ("Dead Inventory").

------

## 3. Stage 2: Data Sanitization

After collecting raw events, the data is sanitized to remove statistical outliers.

### Symmetrical Outlier Rejection
To prevent anomalous prices (e.g., penny books or repricer errors) from skewing the results:
1.  Calculates **Q1** (25th percentile) and **Q3** (75th percentile) of all inferred prices.
2.  Calculates **IQR** (Interquartile Range).
3.  Removes any sale price outside the range `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`.
4.  **Result:** A list of "sane" sale events.

------

## 4. Stage 3: Price Calculation

### A. The "List at" Price (Peak Season)
This determines the recommended listing price.

1.  **Seasonality Identification:** Groups sane sales by month. Identifies the **Peak Month** (highest median price).
2.  **Price Determination:**
    -   **Primary:** Calculates the **Mode** (most frequent price) during the Peak Month.
    -   **Fallback 1:** If no distinct mode exists, uses the **Median**.
    -   **Rescue (Sparse Sales):** If Inferred Sales < **3** (insufficient data), the system uses the **Median** of any available inferred sales (1-2 events) because they still represent *true* sales.
    -   *(Note: The previous "Keepa Stats Fallback" to listing averages was entirely removed in March 2026 to guarantee all profits are based on true sales.)*
3.  **Amazon Ceiling Logic:**
    -   To ensure competitiveness, the "List at" price is capped at **90%** of the lowest Amazon "New" price.
    -   Comparator: `Min(Amazon Current, Amazon 180-day Avg, Amazon 365-day Avg)`.
    -   If `List at > Ceiling`, it is reduced to the Ceiling value.
4.  **AI Reasonableness Check:**
    -   **Primary Check:** For standard inferred prices, the calculated price is sent to **xAI (Grok)** along with the book's title, category, **Binding**, **Page Count**, **Image URL**, and **Rank**.
    -   **Prompt Context:** The prompt explicitly instructs the AI that for seasonal items (especially Textbooks), a Peak Season price can validly be **200-400% higher** than the 3-Year Average to prevent false positive rejections.
    -   **Fallback Exception (Feb 2026):** If the price source is **"Inferred Sales (Sparse)"**, the AI Reasonableness Check is conditionally **SKIPPED** to prevent false rejections.
        -   **Suspiciously High Markup Check (Mar 2026):** If the calculated price (from *any* source, not just fallbacks) is **> 300% (3x)** of the current Used price, the deal is flagged as "Suspiciously High". The AI Reasonableness Check is **FORCED** (not skipped) to prevent accepting inflated prices caused by sparse data or market manipulation.
        -   **Hard Ceiling Safety (Mar 2026):** To prevent astronomical fake profits (e.g., a $4,000 "List At" price), any calculated list price exceeding **$1,500** is automatically and immediately rejected without even querying the AI.
        -   *Safety:* The AI prompt explicitly instructs the LLM that any used book price over $500 requires intense scrutiny, and prices over $1,000 are almost always unreasonable.
    -   If the AI rejects a price (either a standard one or a forced fallback check), the deal is invalidated (and subsequently persisted as incomplete data).

### B. 1-Year Average (`1yr. Avg.`)
Used for the "Percent Down" and "Trend" calculations.

1.  Filters the sane sales list to include only those from the **last 365 days**.
2.  Calculates the **Mean** of these prices.
3.  **Threshold:** Requires at least **1** inferred sale.
4.  **No fallback.** If no inferred sale falls inside the last 365 days, the function
    returns `None`, and the deal is persisted as **incomplete data** (filtered from
    the UI on every branch of `/api/deals` and `/api/deal-count`). This covers two
    distinct cases that reach the same answer: zero inferred sales at all, and
    inferred sales that are all older than 365 days.

    *Removed 2026-09-11 (audit B-6): this step used to fall through to
    `max(stats.avg365[2, 19, 20, 21, 22])`. See the Critical Warning above. Do not
    reintroduce it.*

> **A consequence worth knowing.** `List at` is computed over a **3-year** window and
> `1yr. Avg.` over a **1-year** window, so a book whose only inferred sales are older
> than 365 days now yields a valid `List at` with a `NULL` `1yr. Avg.` That
> combination was impossible while the fallback existed and is now expected. It is
> why `1yr_Avg IS NULL` is no longer a usable damage fingerprint, and why
> `recover_damaged_deals.py` was retired to `Archive/scripts/` — its mandatory
> invariant asserted that exact combination never occurs.

### C. Inferred Sale Count (`Inferred_Sale_Count`)
The number of sane inferred sale events the pricing branch actually used: post-IQR on
the algorithmic path, raw on the XAI-rescue path (which returns before sanitisation).

*   **Written by:** `analyze_sales_performance`, on **every** return branch including
    the zero-sale rejection, and persisted by `_process_single_deal`.
*   **Heavy path only.** The lightweight update preserves the stored value rather than
    recomputing it, because recomputing needs Keepa `csv` history that a light fetch
    does not carry.
*   **`0` and `NULL` are different answers.** `0` means "computed, and there were
    none". `NULL` means "never computed" — a row that predates this column, or one
    only ever touched by the light path. **`NULL` must never be read as zero and must
    never be used to hide a deal.**
*   **Why it exists:** nothing else in the schema records it. `Deal Trust` stores the
    *ratio* `sane_sales / offer_drops`, from which neither term is recoverable, and
    `Recent Inferred Sale Price` stores one price. Before this column, separating a
    one-sale deal from a many-sale one required re-fetching Keepa history at roughly
    20 tokens per ASIN.

------

## Key Evolution & "Hard-Won" Lessons

1.  **Mean vs Median:** We switched from Median to **Mean** for the 1-Year Average to better reflect the true market value across all transactions, after outlier removal proved effective.
2.  **Mode for Peak:** We use **Mode** for the "List at" price because arbitrage sellers often target a specific "standard" market price that occurs frequently, rather than an average of fluctuations.
3.  **Strict Validation with Persistence:** The AI check and the "Missing List at" exclusion are the primary filters. If the system cannot confidently determine a safe listing price, it **persists the deal as incomplete** (for potential future recovery) but filters it from the user dashboard to maintain a clean experience.
4.  **240-Hour Window:** Expanding the correlation window from 168h to 240h significantly improved capture rates for "Near Miss" sales events where rank reporting lagged behind offer drops.
5.  **The Lowest-Offer Series Is Not A Sale Price (Sept 2026):** `csv[1]` / `csv[2]`
    record the cheapest *listing*, so the moment a copy sells they describe the copy
    that did **not** sell. Any "nearest price point" rule therefore has a bias
    toward the higher number, and the bias is largest exactly where it hurts most —
    on a cheap copy under an expensive one. Read a change-log series as "the value
    in force **before** the event", never as "the value at the event".

------

## 5. Verification Case Study: The "Missing Data" Investigation (Feb 2026)

In February 2026, users reported that several deals appeared on the dashboard with missing data (e.g., `1yr Avg: -`) or negative profit, despite Keepa data seemingly being available. An in-depth investigation was conducted to determine if the *calculation logic* was flawed.

### Methodology
A diagnostic script (`tests/trace_1yr_avg.py`) was created to trace the exact execution of the logic on ASIN `1455616133`, one of the reported "missing data" items.

### Findings
1.  **Raw History:** The script found 1286 rank history points and 100 offer count points (valid data availability).
2.  **Inference Logic:**
    *   Detected **46** raw offer drops.
    *   Successfully correlated **28** of them with a Rank Drop within the 240-hour window.
3.  **Sanitization:** 8 outliers were removed using the IQR method.
4.  **Result:**
    *   **Sales in Last 365 Days:** 28 confirmed sales.
    *   **Calculated 1yr Avg:** **$54.38**.

### Conclusion
The calculation logic is **sound**. The data *does* exist, and the algorithm *can* find it. The reason these deals appeared broken on the dashboard was **Data Ingestion Stagnation** (deals getting stuck in a "lightweight update" loop that never re-fetched the full history needed for the calculation), not a flaw in the math itself.

### Resolution
We implemented a **"Zombie Data Defense"** strategy in the `Smart Ingestor`. The system now detects these "Zombie" deals (missing data) and forces a full re-fetch (heavy update) to attempt to repair them. Additionally, deals that truly lack data or have zero profit are now **persisted** (filtered from the UI) to allow for lightweight updates, rather than being rejected and entering an infinite re-fetch loop.
