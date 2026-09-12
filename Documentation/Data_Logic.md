# Data Logic and Column Definitions

This document serves as the canonical source of truth for how each data column in the `deals.db` database is populated, calculated, and transformed. Its purpose is to prevent regressions and provide a clear reference for future development.

For visual presentation rules (formatting, abbreviations, column order), please refer to **`Dashboard_Specification.md`**.

---

## Data Processing Workflow (Calculation Pipeline)

The data for each deal is generated in a multi-stage pipeline orchestrated by the `_process_single_deal` function in `keepa_deals/processing.py`. If a product fails certain critical data quality checks at any stage, its processing is halted, and it is excluded from the database.

1.  **Extraction (Raw Data)**:
    *   Basic attributes (ASIN, Title, Category) are pulled from the Keepa `/product` API.
    *   **Sales Rank**: Extracted from `stats.current[3]`. Falls back to `csv[3]` (history) or `salesRanks` dict if the current stats are missing.
    *   **Amazon Prices**: Extracts `Amazon Current` (using `stats.current[0]`), `Amazon 180-day Avg`, and `Amazon 365-day Avg` for price ceiling logic.
    *   **Batching:** Uses a **Decoupled Batching Strategy** (Smart Ingestor v3.0):
        *   **Peek (Discovery):** 50 ASINs per batch at a refill rate of 30/min or better, scaling down to **15** below 30/min, **20** below 20/min, and **1** below 10/min. *(Corrected 2026-09-12: this line previously omitted the < 30/min tier, which is the one production runs in — the live Keepa plan reports 25/min, so the real peek batch is 15. See `System_Architecture.md` §3.A for the full table and the token arithmetic.)*
        *   **Peek Filter:** Rejects dead inventory, but accepts items with as few as **1 sale rank drop per year** (down from 4) to capture slow-moving "Silver Standard" candidates.
        *   **Commit (Analysis):** 5 ASINs per batch.

2.  **Seller & Price Analysis**:
    *   **Logic:** `keepa_deals/seller_info.py` iterates through the live `offers` array.
    *   **Selection:** It finds the "Used" offer (Conditions: Like New, Very Good, Good, Acceptable) with the **lowest total price** (Price + Shipping).
    *   **Ghost Deal Prevention:** Strictly **rejects** Merchant Fulfilled (MFN) offers where the shipping cost is Unknown (`-1`), as these often mask high actual costs. FBA offers with unknown shipping default to $0.
    *   **Exclusion:** If no valid "Used" offer is found, the deal is dropped.
    *   **Optimization:** Fetches seller details **only** for this single winning seller ID to minimize API calls.
    *   **Output:** `Price Now`, `Seller`, `Seller ID`, `Seller_Quality_Score`.

    **CRITICAL INTEGRITY CHECK (Feb 2026):**
    *   **Zero Profit & Missing Data Persistence:** Deals with `Profit <= 0` or missing critical fields like `List at` / `1yr. Avg.` are now **persisted** to the database rather than rejected. This allows the system to track potentially valuable items and update them via lightweight scans if prices improve.
    *   **Dashboard Filtering:** While these "unprofitable" or "incomplete" deals exist in the database, they are strictly **filtered out** from the user-facing Dashboard API to ensure a clean user experience.
    *   **Amazon Ceiling Check (Lightweight Updates):** When a deal is updated via `_process_lightweight_update`, the system enforces a safety cap: If `List at` > (Amazon New Price * 0.90), the list price is clamped down to that ceiling. This prevents deals from retaining unrealistic profit estimates when the market price drops.
    *   **Self-Healing Persistence:** The Smart Ingestor previously forced a **Heavy Re-fetch** for "Zombie" deals (missing critical data), often causing infinite loops. Now, these deals are **persisted** as-is and flagged for **Lightweight Updates**, allowing them to be repaired naturally over time without wasting tokens.

    **DB COLUMN NAMING CONTRACT (Sept 2026):**
    *   **One namespace per row dictionary.** The deals table is named with **sanitized** column names (`List_at`, `1yr_Avg`, `Sales_Rank_Current`, `All_in_Cost`), produced by `sanitize_col_name` in `keepa_deals/db_utils.py`. The field functions in `stable_products.py` / `new_analytics.py` / `stable_deals.py` return their values under the `headers.json` **display** name (`List at`, `Sales Rank - Current`, `All-in Cost`).
    *   **Heavy path (`_process_single_deal`)** builds a fresh row keyed by **display** names. That is correct and unchanged. In `smart_ingestor.run()` heavy and light rows share one upsert batch, so heavy rows are re-keyed with `to_db_keys` before being appended.
    *   **Light path (`_process_lightweight_update`)** starts from `dict(sqlite3.Row)` off `SELECT * FROM deals`, so it is keyed by **sanitized** names. Every field-function result merged into it must go through `_merge_db_keyed` so the row stays in a single namespace. Mixing the two namespaces in one dictionary is what caused the Sept 2026 data loss described below.
    *   **Both Smart Ingestor upsert sites** (main Light Update and Stale Rescue) call the shared `upsert_deal_rows` helper in `db_utils.py`, which reads rows by sanitized column name. Do not hand-roll the upsert SQL at a call site.
    *   **A no-data sentinel never overwrites a stored value.** Every field function reports "I could not compute this" *in band*, by returning the string `-` (or `''` / `N/A`) under its normal key, rather than by omitting the key. `_merge_db_keyed` therefore **skips** those values instead of writing them, because the row it is merging into is an existing DB row that already holds whatever the last successful pass computed. See "LIGHTWEIGHT PRESERVATION RULE" below.
    *   **The sentinel test is not a falsiness test.** `0`, `0.0` and `'0'` are real readings — an offer count of zero is data, and `get_offer_count_trend` returns the string `'0'` for it, not `-`. A `if not value` guard would discard those and silently freeze the stored count at its last non-zero value. `_is_no_data` in `processing.py` checks for the sentinel strings explicitly.

    **DATA LOSS INCIDENT (Sept 2026) — lightweight upsert key mismatch:**
    *   The main Light Update upsert read values by **display** name off a row keyed by **sanitized** names. 215 of the 246 columns resolved to `None` and were written as `NULL` on every light update, including `List_at`, `Price_Now`, `1yr_Avg`, `Deal_Trust`, `Total_AMZ_fees`, `Peak_Season` and `Trough_Season`. Affected rows disappear silently from the Deals Dashboard because `/api/deals` filters `List_at IS NOT NULL`; the grid does not empty, rows just stop appearing.
    *   The Stale Rescue upsert had the mirror defect: it read sanitized names, so the freshly computed rank, offer counts and `All_in_Cost` (written under display names) were discarded and the **old** values were written back — alongside a **new** `Profit` and `Margin` computed from the new cost. Stored rows failed their own identity: `Profit != List_at - All_in_Cost - Total_AMZ_fees`.
    *   Both are fixed. `tests/test_lightweight_upsert_preservation.py` locks the contract by building the schema from `headers.json` through `sanitize_col_name` and calling the production upsert helper, so a wrong key convention on either side fails the suite.

    **LIGHTWEIGHT PRESERVATION RULE (Sept 2026):**
    *   **When a lightweight fetch cannot compute a value, the stored value is kept and the dashboard shows the last good reading.** It is never replaced with a blank.
    *   **Know what "last good reading" can mean.** On the main Light Update the preserved value is at most a few hours old, because the row is being refreshed from the live deal feed. **On the Stale Rescue it can be days old and is still presented as current.** These rows are by definition ones the deal feed has stopped returning, and every rescue pass refreshes `last_seen_utc`, so a row the rescue keeps reaching is never reaped by the Janitor and can carry a rank, an offer count and an **Ago** value from its last successful heavy pass with nothing on screen saying so. **A row the rescue does not reach in time is deleted at 72h instead.** Until the September 2026 cutoff-format fix that was the common case, not the rare one: the rescue's eligibility check skipped any row whose UTC date matched the cutoff's, so rows reached the Janitor's deadline unrescued. See "Stale Deal Rescue" in `System_Architecture.md`. That is the accepted cost of the rule. It is still the better option, because the alternative writes `NULL` into `Sales_Rank_Current`, which loses the last known value *and* drops the row out of the **Max. Sales Rank** filter entirely.
    *   **Six columns are exposed to this**: `Sales_Rank_Current`, `Drops`, `Offers`, `Offers_180`, `Offers_365` and `last_price_change`. Five are merged through `_merge_db_keyed`. `Drops` is the exception: its DB column name is not a sanitization of the field function's key (`Sales Rank - Drops last 30 days`), so it is written through an explicit mapping that applies the same guard itself. `All_in_Cost` and `Min_Listing_Price` are **not** exposed — they are always computed floats with no sentinel path, and are written directly rather than merged.
    *   **The Stale Rescue is where this bites hardest.** It fetches with `history=0` (no `csv`) *and* has no Keepa deal object to merge (no `currentSince`), because its ASINs are precisely the ones the deal feed has stopped returning — that is why they went stale. `last_price_change` therefore has **no source at all** on that path and returns `-` on every single call. The main Light Update is unaffected: it merges the deal object into the product first, which supplies `currentSince`.
    *   **What went wrong:** the September 2026 upsert fix moved all seven values the light path computes onto sanitized DB column names — five through `_merge_db_keyed`, and `All_in_Cost` and `Min_Listing_Price` as direct writes in the business-math block. That was correct, and it meant the Stale Rescue began *persisting* those values instead of discarding them. It also meant persisting the unconditional `-` that `last_price_change` returns on that path, which replaced a good heavy-path timestamp with a dash on **1,948** rows and nulled `Sales_Rank_Current` on 14 more (`clean_numeric_values` casts `-` to `int`, fails, and stores `NULL`). Before the fix the sentinel had been discarded along with the genuinely fresh values, which masked it.
    *   **Recovery is passive, not scripted.** A blanked row heals the next time Keepa's deal feed surfaces it, because that routes it through the main Light Update, which has a working timestamp source. Chronically stale rows are by definition the ones the feed is not surfacing, so expect a slow drain rather than a clean sweep. There is no way to recompute the value on the rescue path itself.
    *   **Guarded by** the `StaleRescueSentinelTest` cases in `tests/test_lightweight_upsert_preservation.py`. Those drive `_process_lightweight_update` with the **real** field functions and a bare `fetch_current_stats_batch`-shaped product, not with patched return values. The pre-existing tests patched in fresh values and so only ever exercised the happy path, which is how this shipped.

3.  **Inferred Sales (The Engine)**:
    *   **Logic:** `keepa_deals/stable_calculations.py` -> `infer_sale_events`.
    *   **Mechanism:** A sale is "inferred" when a drop in the **Offer Count** (someone bought a copy) is followed by a drop in **Sales Rank** (Amazon registered the sale) within a **240-hour** (10-day) window.
    *   **XAI Rescue (Hidden Sales):** If the standard mechanism finds 0 confirmed sales or no offer drops, it triggers an **xAI Rescue**. The system sends ~365 days of history to the LLM to identify "Hidden Sales" (Rank drops without Offer drops), rescuing valid deals that would otherwise be rejected.
    *   **Sparse Data Lookahead:** If no rank drop is found immediately, the system looks ahead **30 days**. If the next available rank is lower (better) than the rank before the offer drop, a sale is inferred. This allows capturing sales for slow-moving items with sparse rank history.
    *   **Sparse Sales Rescue:** If fewer than **3** inferred sales are found but at least 1, the system uses the **Median** of those 1-2 events as a "Sparse Rescue" price. They are TRUE inferred sales, just few. *(This previously read "if fallback stats are missing", which described a condition the code never had - the branch turns on the sale count alone, `MIN_SALES_FOR_ANALYSIS = 3`.)*
    *   **Output:** A list of `sale_events` used for all downstream analytics.

4.  **Analytics & Seasonality**:
    *   **Logic:** `keepa_deals/new_analytics.py` and `seasonality_classifier.py`.
    *   **1yr. Avg.:** The mean price of all inferred sales in the last 365 days. **Inferred sales only — there is no fallback** (the `avg365` listing-average fallback was removed 2026-09-11, audit B-6).
    *   **Exclusion:** If no inferred sale falls inside the last 365 days, `1yr. Avg.` is None and the deal is persisted as incomplete data (filtered from the UI). Note this includes deals that DO have inferred sales, just older ones — those keep a valid `List at` from the 3-year window alongside a NULL `1yr. Avg.`
    *   **Inferred Sale Count:** The number of sane sale events the pricing branch used, persisted on the heavy path only. `0` means "computed, none found"; `NULL` means "never computed" and must never be read as zero or used to hide a deal.
    *   **Seasonality:** AI (`grok-4-fast-reasoning`) classifies the book (e.g., "Fall Semester") based on title, category, and historical peak sales months.

5.  **Price Benchmarks ("List at" & "Trough")**:
    *   **Logic:** `keepa_deals/stable_calculations.py`.
    *   **List at (Peak):**
        *   **Primary:** Determines the **Mode** (most frequent) sale price during the book's calculated **Peak Season**.
        *   **Rescue (Sparse Sales):** If Inferred Sales < 3 (but > 0), the system uses the **Median** of any available inferred sales (1-2 events) because they still represent *true* sales.
        *   *(Note: The previous "Keepa Stats Fallback" to listing averages was entirely removed in March 2026 to guarantee all profits are based on true sales. Deals with 0 inferred sales are rejected.)*
    *   **Expected Trough Price:**
        *   **Calculation:** Determines the **Median** sale price during the book's calculated **Trough Season** (lowest median price month).
    *   **Validation Pipeline:** **ALL** prices (Primary or Fallback) must pass safety checks:
        1.  **Amazon Ceiling:** Capped at 90% of the lowest Amazon "New" price (Min of Current, 180d avg, 365d avg). This is enforced for ALL prices.
        2.  **XAI Reasonableness Check:** Queries AI (`grok-4-fast-reasoning`) with context.
            *   **Exception:** If the price source is **Inferred Sales (Sparse)** (1-2 true sales, thin context), this check is conditionally **SKIPPED**. *(The "Keepa Stats Fallback" half of this exception was removed on 2026-09-11 with the fallback itself — no code path produces that source any more.)*
            *   **Suspiciously High:** If the price is **> 300% (3x)** of the current Used price, the check is **FORCED**, overriding the sparse skip, to prevent accepting manipulated prices.
    *   **Exclusion:** If validation fails, the price is invalidated (potentially leading to persistence as incomplete data).

6.  **Business Math**:
    *   **Logic:** `keepa_deals/business_calculations.py`.
    *   **Inputs:** `buy_cost_paid` (or Estimated Price Now + Tax + Shipping), `List at`, Amazon Fees (FBA + Referral), User Settings (Prep Fee).
    *   **Output:** `All-in Cost`, `Profit`, `Margin`, `Min. Listing Price`.

7.  **Restriction Check (Gating)**:
    *   **Logic:** `keepa_deals/sp_api_tasks.py` -> `check_all_restrictions_for_user`.
    *   **Mechanism:** Queries Amazon SP-API `getListingsRestrictions`.
    *   **Condition-Aware:** Maps the deal's condition (e.g., "Used - Like New") to the specific SP-API enum (`used_like_new`) to check gating for that specific condition.
    *   **Output:** `is_restricted` (Bool or -1 for error), `approval_url`.

---

## Column Breakdown

### Core Deal & Product Information

-   **`ASIN`**: Directly from Keepa.
-   **`Title`**: Directly from Keepa.
-   **`Deal found`**: ISO timestamp of when the deal was processed.
-   **`last_update`**: **Intentionally unpopulated. Always `NULL`, on every row, by owner decision (2026-09-12).** `FUNCTION_LIST[10]` is `None`; nothing writes this column. It exists in `headers.json` and therefore in the schema, and it is returned in the `/api/deals` row payload, where nothing reads it — not the dashboard, not any filter, not any sort.
    -   **Why it is not populated.** `stable_deals.last_update` is still in the file and implements the three-source MAX in `AGENTS.md` §7.3, but wiring it into the extraction loop would produce the wrong value three ways: only 1 of its 3 sources is reachable through a single-positional-argument call; the loop is heavy-path only, so the column would be populated on newly discovered rows and `NULL` on light and Stale Rescue rows; and it renders Toronto-local, space-separated time where every other timestamp writer uses UTC isoformat — the same mismatch behind the Stale Rescue cutoff defect of PR #332. A half-populated local-time column nothing reads is worse than a `NULL` one.
    -   **It was never populated, and not on purpose until now.** `logger_param` had no default, so the loop's `func(product_data)` raised `TypeError` on every heavy-path deal and the upsert bound the missing key as `NULL`. A `@retry(stop_max_attempt_number=3, wait_fixed=5000)` turned that permanent error into **10 seconds of sleep per newly discovered deal**. Both are gone; the slot stays `None`. Pinned by `tests/test_field_mappings_call_contract.py`.

-   **`last_price_change`**: Timestamp of the most recent price change for any "Used" item. Prioritizes `product.csv` history, falls back to `deal.currentSince`.
    -   **Both sources are absent on the Stale Rescue path.** `history=0` suppresses `csv`, and the rescue has no Keepa deal object to supply `currentSince`. The function returns its `-` sentinel there on every call, so the stored timestamp is preserved instead. See "LIGHTWEIGHT PRESERVATION RULE" above.

### Seller and Offer Information

-   **`Price Now`**:
    -   **Source**: `keepa_deals/seller_info.py`.
    -   **Logic**: Lowest total price (Item + Shipping) of the best "Used" offer.

-   **`Seller`**:
    -   **Source**: `keepa_deals/processing.py` (via `seller_info`).
    -   **Logic**: The `sellerName` of the winning offer. Falls back to `sellerId` if name is missing.
    -   **Smart Preservation:** During lightweight updates (where name is unavailable), the system checks the winning `sellerId`. If it matches the existing record's `Seller ID`, the existing human-readable name is **preserved**. If IDs differ, the field is updated to the new ID.

-   **`Seller_Quality_Score` (Trust)**:
    -   **Source**: `keepa_deals/stable_calculations.py`.
    -   **Logic**: **Wilson Score Confidence Interval**. Uses `rating` (0-500) and `ratingCount`.
    -   **Range**: 0.0 to 1.0 (Probability).
    -   **Display**: Dashboard converts this 0.0-1.0 float into a "X / 10" integer format by multiplying by 10 (e.g., 0.95 -> 10 / 10).

-   **`Condition`**:
    -   **Source**: `keepa_deals/stable_deals.py`.
    -   **Logic**: Returns the condition of the winning offer (e.g., "Used, very good").
    -   **Transformation**: Converted to numeric code (1-5) for DB storage, then re-mapped to abbreviations (e.g., "U - VG") by the API for display.

-   **`Binding`**:
    -   **Source**: `keepa_deals/processing.py` -> `clean_binding_text`.
    -   **Logic**: Replaces underscores and hyphens with spaces, applies Title Case (e.g., `mass_market` -> "Mass Market").
    -   **Display**: Dashboard truncates to 95px with ellipsis, full text on hover.

### Advanced Analytics (Rank & Offers)

-   **`Sales Rank - Drops` (30/180/365)**:
    -   **Source**: `keepa_deals/stable_products.py`.
    -   **Logic**: The integer count of drops in Sales Rank over the respective period.
    -   **Periods**: 30 days (`Drops` on dashboard), 180 days, and 365 days.

-   **`Used Offer Count - Avg` (180/365)**:
    -   **Source**: `keepa_deals/stable_products.py`.
    -   **Logic**: The average number of used offers over the last 180 and 365 days.

-   **`Offers` Trend**:
    -   **Source**: `keepa_deals/new_analytics.py`.
    -   **Current**: Compares Current Count vs 30-day Avg.
    -   **180 Days**: Compares 90-day Avg vs 180-day Avg.
    -   **365 Days**: Compares 180-day Avg vs 365-day Avg.
    -   **Deduplication Comparison (Pass 1)**: `get_offer_count_trend_from_flat` safely parses the raw string columns and compares Current Count vs 365-day Avg (since 30-day avg is intentionally nullified for storage optimization).
    -   **Output**: Count + Arrow (e.g., "12 ↘"). Green ↘ (Falling) is good; Red ↗ (Rising) is bad.

### Price Analytics

-   **`1yr. Avg.`**:
    -   **Source**: `keepa_deals/new_analytics.py`.
    -   **Logic**: Mean of inferred sale prices over last 365 days.
    -   **Threshold**: Requires **at least 1** inferred sale inside that window. If none, returns `None`.
    -   **No fallback**: never a listing average, an Amazon price, a Keepa list price or a default. Removed 2026-09-11 (audit B-6).

-   **`Inferred Sale Count`**:
    -   **Source**: `keepa_deals/stable_calculations.py` (`analyze_sales_performance`), persisted by `_process_single_deal`.
    -   **Logic**: Count of the sane sale events the pricing branch used — post-IQR on the algorithmic path, raw on the XAI-rescue path.
    -   **Written on the heavy path only.** The light path preserves the stored value; recomputing needs Keepa `csv` history a light fetch does not carry.
    -   **`0` vs `NULL`**: `0` means computed-and-none-found; `NULL` means never computed (a legacy row, or one only ever touched by the light path). **`NULL` must never be read as zero, and neither value is used to hide a deal.**

-   **`Percent Down` (% ⇩)**:
    -   **Source**: `keepa_deals/new_analytics.py`.
    -   **Logic**: `((1yr. Avg. - Price Now) / 1yr. Avg.) * 100`.
    -   **Rule**: If `Price Now` > `1yr. Avg.`, returns 0%.

-   **`Trend`**:
    -   **Source**: `keepa_deals/new_analytics.py`.
    -   **Logic**: Analyzes a sample (size 3-10) of recent **unique** price points.
    -   **Output**:
        -   `⇧` (Up) if last price > first price of sample.
        -   `⇩` (Down) if last price < first price.
        -   `⇨` (Flat) otherwise.
    -   **Dashboard**: Merged into "Changed" column (Arrow + Time).

-   **`Deal Trust` (Deal Trust)**:
    -   **Source**: `keepa_deals/stable_calculations.py`.
    -   **Logic**: `(Count of Inferred Sales / Count of Offer Drops) * 100`.
    -   **Meaning**: High % means offer drops reliably correlate with sales rank drops.
    -   **Non-numeric state**: `'-'`, returned when `total_offer_drops == 0`. That is the XAI "no offer drops" rescue, where every sale came from the model and there is no denominator to score. **`/api/deals` casts it with `CAST(REPLACE("Deal_Trust", '%', '') AS REAL)`, which yields `0.0`, so any non-zero Min. Deal Trust filter silently excludes those rows.**
    -   **Removed**: the `"Low (Est.)"` state. It marked a row whose `1yr. Avg.` came from the `avg365` listing-average fallback; that fallback was removed on 2026-09-11 (audit B-6) and the marked rows were deleted by `cleanup_low_est_rows.py`. The CAST above is deliberately **unchanged** — it is still needed for the `'-'` state.

### AI-Driven Seasonality and Pricing

-   **`Detailed_Seasonality`**:
    -   **Source**: `keepa_deals/seasonality_classifier.py`.
    -   **Logic**: AI classification based on Title, Category, and Peak Months.

-   **`List at`**:
    -   **Source**: `keepa_deals/stable_calculations.py`.
    -   **Logic**: **Mode** of peak season prices, falling back to the peak-season **Median** when no distinct mode exists. With 1-2 sales, the Sparse Rescue median. **Inferred sales only.** *(This previously read "or `Used - 90d avg` fallback if high velocity" — that fallback was deleted in March 2026 and has not existed since.)*
    -   **Constraint**: Capped at 90% of `Min(Amazon Current, Amazon 180d avg, Amazon 365d avg)`.
    -   **AI Check**: Validated by `grok-4-fast-reasoning`, skipped for `Inferred Sales (Sparse)` unless the 3x-of-current-used rule forces it, and skipped when the Amazon ceiling clamped the price.

-   **`Expected Trough Price`**:
    -   **Source**: `keepa_deals/stable_calculations.py`.
    -   **Logic**: **Median** of inferred sale prices during the identified Trough Month.

-   **`Gated` (Restriction Status)**:
    -   **Source**: `user_restrictions` table (via SP-API).
    -   **States**:
        -   `Null/None`: Pending check (Spinner).
        -   `0 (False)`: Not Restricted (Green Check).
        -   `1 (True)`: Restricted (Red X).
        -   `-1`: API Error (Broken Icon).
    -   **Approval URL Fallback**: If restricted but no specific link is returned, defaults to `https://sellercentral.amazon.com/hz/approvalrequest?asin={ASIN}`.

-   **`My Mentor` (Overlay Feature)**:
    -   **Source**: `keepa_deals/ava_advisor.py`.
    -   **Logic**: Real-time call to `grok-4-fast-reasoning` generating specific, actionable advice (50-80 words).
    -   **Context**: Uses deal metrics + `strategies.json`.

### Business & Financial Metrics

-   **`All-in Cost`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `buy_cost_paid + Prep Fee`. (Note: For Dashboard estimates, `buy_cost_paid` is estimated as Price Now + Tax + Shipping).
    -   **Explanation**: This represents the initial, out-of-pocket acquisition cost required to purchase the book and send it to Amazon. Prep fee is the only cost added on top of `buy_cost_paid`. It intentionally **excludes** Amazon selling fees (FBA and Referral fees). Amazon fees are deducted from the gross revenue at the time of sale, rather than being an upfront cash expense. Including them here would artificially inflate the baseline cost, thereby miscalculating (crushing) the Return on Investment (ROI).

-   **`Profit`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `List at - All-in Cost - Total AMZ fees`.
    -   **Explanation**: This calculates the projected net profit (an estimate until actual sale). While Amazon fees are excluded from the initial `All-in Cost` investment, they are correctly subtracted from the gross revenue (`List at`) alongside the out-of-pocket costs to accurately predict your final take-home profit. (`Total AMZ fees` = FBA Fee + Referral Fee. Note: Referral Fee is calculated based on the final **List at** price, not the buy cost).

-   **`Margin`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `(Profit / List at) * 100`.

-   **`ROI` (Return on Investment)**:
    -   **Source**: Dynamically calculated on frontend (`dashboard.html`, `tracking.html`) and backend endpoints (`wsgi_handler.py`).
    -   **Formula**: `(Profit / All-in Cost) * 100`.
    -   **Explanation**: Represents the cash-on-cash leverage. It is not stored in the database schema.

-   **`Tracking & Potential Buys Inline Calculations`**:
    -   **Source**: `/api/tracking/potential/<int:item_id>` (`wsgi_handler.py`).
    -   **Logic**: Users can edit the `buy_cost_paid` inline for Potential Buys. This triggers an immediate recalculation of `All-in Cost`, `Profit`, `Margin`, and `ROI` using the updated cost, and sets the `buy_cost_confirmed` boolean to true in the `inventory_ledger`. This provides exact financial metrics before purchase rather than relying on Keepa's scrape-time estimates.

-   **`Realized Profit (Sales History)`**:
    -   **Source**: `/api/tracking/sales` (`wsgi_handler.py`).
    -   **Logic**: Realized profit is estimated by merging the true `sale_price` from the `sales_ledger` with the original `buy_cost` from the `inventory_ledger` (via FIFO matching in `reconciliation_log`).
    -   **Note**: The "Fees" column was removed because the SP-API Orders endpoint does not provide precise per-item fees (which requires a Finances API integration).

-   **`Min. Listing Price`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `(All-in Cost + FBA Fee) / (1 - Default Markup % - Referral Fee %)`.

### AI Knowledge Extraction (Guided Learning)

-   **`extract_strategies`**:
    -   **Source**: `wsgi_handler.py`.
    -   **Prompt**: Extracts specific, actionable rules/numbers.
    -   **Model**: `grok-4-fast-reasoning` (Temperature 0.2).
    -   **Logic**: Parses input text for conditions like "Rank < X" or "Profit > Y".

-   **`extract_conceptual_ideas`**:
    -   **Source**: `wsgi_handler.py`.
    -   **Prompt**: Extracts high-level mental models and "why" logic.
    -   **Model**: `grok-4-fast-reasoning` (Temperature 0.3).
    -   **Logic**: Focuses on qualitative insights.

---

## The "Janitor" & Data Freshness

-   **Trigger**: Every 4 hours or Manual "Refresh Deals".
-   **Logic**: Deletes deals where `last_seen_utc` is older than **72 hours**.
-   **Purpose**: Prevents stale deals from cluttering the dashboard while giving the backfiller enough time (3 days) to update them.

---

## Data Standards & Epochs

### Keepa Timestamps
-   **Epoch:** `2011-01-01` (January 1st, 2011).
-   **Note:** Keepa uses different epochs for different API fields. For the fields used in this system (e.g., `stats.current`, `stats.lastUpdate`), the epoch is 2011. Using the standard Unix epoch (1970) or the Java epoch (2000) will result in incorrect dates.

### Keepa Query Parameters
-   **Standard:** The system uses `dateRange: 4` (All Combined) to retrieve the maximum deal history.
-   **Requirement:** This MUST be paired with `sortType: 4` (Last Update) to ensure the API returns deals with recent updates, rather than stale data from 2015.
