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

2.  **Seller & Price Analysis**:
    *   **Logic:** `keepa_deals/seller_info.py` iterates through the live `offers` array.
    *   **Selection:** It finds the "Used" offer (Conditions: Like New, Very Good, Good, Acceptable) with the **lowest total price** (Price + Shipping).
    *   **Ghost Deal Prevention:** Strictly **rejects** Merchant Fulfilled (MFN) offers where the shipping cost is Unknown (`-1`), as these often mask high actual costs. FBA offers with unknown shipping default to $0.
    *   **Exclusion:** If no valid "Used" offer is found, the deal is dropped.
    *   **Optimization:** Fetches seller details **only** for this single winning seller ID to minimize API calls.
    *   **Output:** `Price Now`, `Seller`, `Seller ID`, `Seller_Quality_Score`.

3.  **Inferred Sales (The Engine)**:
    *   **Logic:** `keepa_deals/stable_calculations.py` -> `infer_sale_events`.
    *   **Mechanism:** A sale is "inferred" when a drop in the **Offer Count** (someone bought a copy) is followed by a drop in **Sales Rank** (Amazon registered the sale) within a **240-hour** (10-day) window.
    *   **Output:** A list of `sale_events` used for all downstream analytics.

4.  **Analytics & Seasonality**:
    *   **Logic:** `keepa_deals/new_analytics.py` and `seasonality_classifier.py`.
    *   **1yr. Avg.:** The mean price of all inferred sales in the last 365 days.
    *   **Exclusion:** If inferred sales < 1 (insufficient data), `1yr. Avg.` is None, and the deal is dropped.
    *   **Seasonality:** AI (`grok-4-fast-reasoning`) classifies the book (e.g., "Fall Semester") based on title, category, and historical peak sales months.

5.  **Price Benchmarks ("List at" & "Trough")**:
    *   **Logic:** `keepa_deals/stable_calculations.py`.
    *   **List at (Peak):**
        *   **Primary:** Determines the **Mode** (most frequent) sale price during the book's calculated **Peak Season**.
        *   **Fallback (High Velocity):** **REMOVED**. The system no longer uses `Used - 90d avg` as a fallback. If no mode/median can be found from confirmed sales, the deal is rejected.
    *   **Expected Trough Price:**
        *   **Calculation:** Determines the **Median** sale price during the book's calculated **Trough Season** (lowest median price month).
    *   **Ceiling Guardrail:** The "List at" price is capped at 90% of the lowest Amazon "New" price (Min of Current, 180d avg, 365d avg).
    *   **Verification:** Queries AI (`grok-4-fast-reasoning`): "Is a peak price of $X.XX reasonable for this book?" Context provided includes Binding, Page Count, Image URL, and Rank.
    *   **Exclusion:** If AI says "No" or calculation fails, the deal is dropped.

6.  **Business Math**:
    *   **Logic:** `keepa_deals/business_calculations.py`.
    *   **Inputs:** `Price Now`, `List at`, Amazon Fees (FBA + Referral), User Settings (Prep, Tax).
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
-   **`last_price_change`**: Timestamp of the most recent price change for any "Used" item. Prioritizes `product.csv` history, falls back to `deal.currentSince`.

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
    -   **Output**: Count + Arrow (e.g., "12 ↘"). Green ↘ (Falling) is good; Red ↗ (Rising) is bad.

### Price Analytics

-   **`1yr. Avg.`**:
    -   **Source**: `keepa_deals/new_analytics.py`.
    -   **Logic**: Mean of inferred sale prices over last 365 days.
    -   **Threshold**: Requires **at least 1** inferred sale. If 0, returns None and deal is excluded.

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

-   **`Profit Confidence` (Profit Trust)**:
    -   **Source**: `keepa_deals/stable_calculations.py`.
    -   **Logic**: `(Count of Inferred Sales / Count of Offer Drops) * 100`.
    -   **Meaning**: High % means offer drops reliably correlate with sales rank drops (confirmed sales). Low % implies noise or fake drops.

### AI-Driven Seasonality and Pricing

-   **`Detailed_Seasonality`**:
    -   **Source**: `keepa_deals/seasonality_classifier.py`.
    -   **Logic**: AI classification based on Title, Category, and Peak Months.

-   **`List at`**:
    -   **Source**: `keepa_deals/stable_calculations.py`.
    -   **Logic**: **Mode** of peak season prices (or `Used - 90d avg` fallback if high velocity).
    -   **Constraint**: Capped at 90% of Amazon New price.
    -   **AI Check**: Validated by `grok-4-fast-reasoning`.

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

-   **`Advice` (Overlay Feature)**:
    -   **Source**: `keepa_deals/ava_advisor.py`.
    -   **Logic**: Real-time call to `grok-4-fast-reasoning` generating specific, actionable advice (50-80 words).
    -   **Context**: Uses deal metrics + `strategies.json`.

### Business & Financial Metrics

-   **`All-in Cost`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `Price Now + Tax + Prep Fee + FBA Fee + Referral Fee + Shipping`.
    -   **Referral Fee**: Calculated based on the **List at** price (not Price Now).

-   **`Profit`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `List at - All-in Cost`.

-   **`Margin`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `(Profit / List at) * 100`.

-   **`Min. Listing Price`**:
    -   **Source**: `keepa_deals/business_calculations.py`.
    -   **Formula**: `All-in Cost / (1 - Default Markup %)`.

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
