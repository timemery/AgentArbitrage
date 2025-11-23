# Data Logic and Column Definitions

This document serves as the canonical source of truth for how each data column in the `deals.db` database and on the dashboard is populated, calculated, and transformed. Its purpose is to prevent regressions and provide a clear reference for future development.

---

## Data Processing Workflow Overview

The data for each deal is generated in a multi-stage pipeline orchestrated by the `_process_single_deal` function in `keepa_deals/processing.py`.

1.  **Initial Data Extraction**: Basic product attributes are extracted directly from the Keepa `/product` API response. Many of these are simple lookups from the `product` object or the `stats` object within it.
2.  **Seller & Price Analysis**: The `offers` array from the API response is analyzed by `keepa_deals/seller_info.py` to find the best (lowest total price) "Used" offer. This determines the `Price Now` and all associated seller information.
3.  **Analytics & Inferred Sales**: The historical `csv` data from the API response is analyzed by `keepa_deals/stable_calculations.py` to infer historical sale events. A sale is inferred when a drop in the offer count is followed by a drop in the sales rank. These inferred sales are the foundation for many advanced analytics.
4.  **AI-Enriched Seasonality**: The book's title, category, and inferred peak/trough sales months are used to query an AI model (`grok-4-fast-reasoning`) in `keepa_deals/seasonality_classifier.py`. The AI chooses the most likely sales season from a predefined list, providing a more nuanced classification than simple keywords.
5.  **Business Calculations**: Finally, `keepa_deals/business_calculations.py` takes all the previously generated data (acquisition price, Amazon fees, AI-suggested list price, user-defined prep costs) to calculate the final financial metrics like `All-in Cost`, `Profit`, and `Margin`.

---

## Column Breakdown

### Core Deal & Product Information

-   **`ASIN`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `get_asin()`
    -   **Logic**: Directly extracted from the `asin` field of the Keepa product data object.

-   **`Title`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `get_title()`
    -   **Logic**: Directly extracted from the `title` field.

-   **`AMZ link`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `amz_link()`
    -   **Logic**: Constructed as a static URL string: `https://www.amazon.com/dp/{ASIN}?psc=1&aod=1`.

-   **`Keepa Link`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `keepa_link()`
    -   **Logic**: Constructed as a static URL string: `https://keepa.com/#!product/1-{ASIN}`.

-   **`Deal found`**:
    -   **Source**: `keepa_deals/stable_deals.py` -> `deal_found()`
    -   **Logic**: Converts the `creationDate` (a Keepa timestamp in minutes) from the `/deal` API response into a full ISO 8601 formatted datetime string, localized to the 'America/Toronto' timezone.

*** Future feature will make this timestamp local to the users timezone, whether they are in Toronto or New Zealand, or any timezone worldwide.

-   **`last update`**:
    -   **Source**: `keepa_deals/stable_deals.py` -> `last_update()`
    -   **Logic**: Takes the **most recent** timestamp from three possible sources in the API data: `product.lastUpdate`, `deal.lastUpdate`, and `stats.lastOffersUpdate`. Converts this timestamp to a `YYYY-MM-DD HH:MM:SS` string in the 'America/Toronto' timezone.

-   **`last price change`**:
    -   **Source**: `keepa_deals/stable_deals.py` -> `last_price_change()`
    -   **Logic**: Specifically finds the most recent price change for **"Used" items (excluding 'Acceptable')**. It prioritizes historical data from `product.csv` and falls back to `deal.currentSince` if necessary. Converts the timestamp to a `YYYY-MM-DD HH:MM:SS` string in the 'America/Toronto' timezone.

*** Most of this should be fine, however we do not want to exclude Acceptable condition books. This was an old specification that I realized would lead to fewer deals, and the user can see the seller trust associated to that listing, and can decide for themselves whether or not this is a good buy, even in acceptable condition.

### Seller and Offer Information

-   **`Price Now`**:
    -   **Source**: `keepa_deals/seller_info.py` -> `_get_best_offer_analysis()`
    -   **Logic**: This is the **lowest total price (item price + shipping)** found by iterating through all "Used" offers in the live `offers` array from the API. If no "Used" offers are found, it falls back to the `stats.current[2]` value and the seller is marked as `(Price from Keepa stats)`.

*** Falbacks are not useful, because if there are no used offers, there are simply no used offers, and so that ASIN should be excluded from collection to the db.

-   **`Best Price`**:
    -   **Source**: Same as `Price Now`.
    -   **Logic**: This column is currently redundant and holds the same value as `Price Now`.

-   **`Shipping Included`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `get_shipping_included()`
    -   **Logic**: Returns 'yes' if a "Used" offer is found with a `shippingCost` of `0` or if the `buyBoxUsedShipping` field in `stats` is `0`. Otherwise, returns 'no'.

-   **`Seller`**:
    -   **Source**: `keepa_deals/seller_info.py` -> `_get_best_offer_analysis()`
    -   **Logic**: The `sellerName` associated with the single offer that was determined to have the lowest total price for `Price Now`. The seller name is retrieved from a pre-fetched seller data cache.

-   **`Seller ID`**:
    -   **Source**: `keepa_deals/seller_info.py` -> `_get_best_offer_analysis()`
    -   **Logic**: The `sellerId` associated with the winning offer for `Price Now`.

-   **`Seller_Quality_Score` (Trust)**:
    -   **Source**: `keepa_deals/seller_info.py` -> `_get_best_offer_analysis()`
    -   **Logic**: Calculated using the **Wilson Score Confidence Interval** via `stable_calculations.calculate_seller_quality_score()`. This provides a more statistically sound rating than a simple average, especially for sellers with few ratings. It uses the `currentRating` and `currentRatingCount` for the seller from the seller data cache. The output is formatted as `X.X/5.0`.

-   **`Condition`**:
    -   **Source**: `keepa_deals/stable_deals.py` -> `get_condition()`
    -   **Logic**: The human-readable condition name (e.g., "good", "very good") associated with the winning offer for `Price Now`.

### Advanced Analytics

-   **`1yr. Avg.`**:
    -   **Source**: `keepa_deals/new_analytics.py` -> `get_1yr_avg_sale_price()`
    -   **Logic**: Calculates the **mean (average)** of all **inferred sale prices** that occurred within the last 365 days.
    -   **Dependency**: Relies on `stable_calculations.infer_sale_events()`.
    -   **Note**: Returns "Too New" if fewer than 3 inferred sales are found in the last year.

*** If fewer than 3 sales are found in the inferred sales, that book is not likely to be a good buy, and so should be excluded from collection to the db.

-   **`% Down`**:
    -   **Source**: `keepa_deals/new_analytics.py` -> `get_percent_discount()`
    -   **Logic**: A simple percentage calculation: `((1yr. Avg. - Best Price) / 1yr. Avg.) * 100`. If `Best Price` is higher than `1yr. Avg.`, it returns `0%`.

-   **`Trend`**:
    -   **Source**: `keepa_deals/new_analytics.py` -> `get_trend()`
    -   **Logic**: Determines the recent price trend (⇧, ⇩, ⇨). It combines the "New" and "Used" price histories, takes a dynamic sample of the most recent unique price points (sample size is larger for lower sales rank books), and compares the first and last price in the sample.

*** There are additional details that define this result... I believe we considered mean, mode median, and settled on one (can't remember which) would provided the best answer... can you provide those additional details in order to ensure that logic is recorded and not lost during a future update?

-   **`Recent Inferred Sale Price`**:
    -   **Source**: `keepa_deals/stable_calculations.py` -> `recent_inferred_sale_price()`
    -   **Logic**: The price of the single most recent inferred sale event.
    -   **Dependency**: Relies on `stable_calculations.infer_sale_events()`.

*** I'm not sure where we show this price in the web UI, or if/how we use it in other columns. Can you clarify? If this is the price we show in the "List at" column, it's not what should be listed there (unless I'm misinterpreting your explanation). The "List at" price is intended to provide the most likley price a book will sell at during its peak selling season. If its a book without a clear season, and sells year round that should still represent the peak price a user can expect to list and sell it at by knowing "what the market will bear" at those peak selling times.   

-   **`Profit Confidence`**:
    -   **Source**: `keepa_deals/stable_calculations.py` -> `profit_confidence()`
    -   **Logic**: Calculates a percentage representing the ratio of "confirmed sale events" to "total offer drops". A high percentage means that most offer drops successfully correlated with a sales rank drop, indicating reliable sales data.
    -   **Dependency**: Relies on `stable_calculations.infer_sale_events()`.

### AI-Driven Seasonality and Pricing

-   **`Peak Season`**:
    -   **Source**: `keepa_deals/stable_calculations.py` -> `get_peak_season()`
    -   **Logic**: After generating a list of inferred sale events, this function groups them by month and finds the month with the highest **median** sale price. It returns the abbreviated month name (e.g., "Aug").

-   **`Trough Season`**:
    -   **Source**: `keepa_deals/stable_calculations.py` -> `get_trough_season()`
    -   **Logic**: Similar to `Peak Season`, but finds the month with the lowest **median** sale price.

-   **`Detailed_Seasonality`**:
    -   **Source**: `keepa_deals/seasonality_classifier.py` -> `classify_seasonality()`
    -   **Logic**: This is a multi-step process:
        1.  It first checks the book's title, category, and publisher against a list of keyword heuristics (e.g., "AP" in title -> "High School AP Textbooks").
        2.  If no heuristic matches, it queries the `grok-4-fast-reasoning` AI model.
        3.  The AI is given the title, category, publisher, and the calculated `Peak Season` and `Trough Season` months. It is then asked to choose the best fit from a predefined list of seasons.
        4.  The AI's response is cached to prevent redundant API calls.

-   **`Sells`**:
    -   **Source**: `keepa_deals/seasonality_classifier.py` -> `get_sells_period()`
    -   **Logic**: A simple dictionary lookup that maps the `Detailed_Seasonality` string to a human-readable selling period (e.g., "Christmas" -> "Nov - Dec").

-   **`List at`**:
    -   **Source**: `keepa_deals/stable_calculations.py` -> `get_list_at_price()`
    -   **Logic**: This is the AI-verified target selling price.
        1.  It first identifies all inferred sale prices that occurred during the `Peak Season`.
        2.  It calculates the statistical **mode** (most frequently occurring price) of those sales. If no clear mode exists, it falls back to the median.
        3.  This calculated price is then sent to the `grok-4-fast-reasoning` AI model for a **reasonableness check**. The AI is asked "Is a peak selling price of $X.XX reasonable for this book?".
        4.  If the AI responds "No", the price is discarded and "Too New" is returned. Otherwise, the calculated price is used.

*** I'm not sure I like the "Too New" lable here as a fallback. If there's truly no way to make an educated guess at what the potential sale price is for this book, we might consider excluding that book from the results rather than listing it with "Too New" since the purpose of this application is to find profitable books, if we cannot predict it's most likley sale price to list it at, we cannot reccommend it as a book worth buying to arbitrage. Are there other things we can do to find a price that MIGHT be good, and then adjust the "Profit Trust" rating to reflect the lack of trust we have in that predicted sale/list price? This is just theoretical, and I'm just looking for ideas. If the best idea is to eliminate that book when we can't provide a trust worthy "List at" price, I'm good with that. The only downside to that is a reduced number of books we can recommend, however it might be better not to list a book we aren't sure will sell at our "List at" price if we're not confident in that number.  

### Business & Financial Metrics

-   **`FBA Pick&Pack Fee`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `get_fba_pick_pack_fee()`
    -   **Logic**: Directly extracted from `product.fbaFees.pickAndPackFee` in the API response.

-   **`Referral Fee %`**:
    -   **Source**: `keepa_deals/stable_products.py` -> `get_referral_fee_percent()`
    -   **Logic**: Extracted from `product.referralFeePercentage` in the API response.

-   **`All-in Cost`**:
    -   **Source**: `keepa_deals/business_calculations.py` -> `calculate_all_in_cost()`
    -   **Logic**: The total estimated cost to acquire and sell the book. The formula is:
        `Price Now` + `Tax` + `Prep Fee` + `Amazon Fees` + `Estimated Shipping`.
    -   **Details**:
        -   `Amazon Fees` = `FBA Pick&Pack Fee` + `Referral Fee`. The `Referral Fee` amount is calculated as `List at` price \* `Referral Fee %`.
        -   `Tax` is calculated based on `Price Now` and the user's tax rate setting.
        -   `Prep Fee` and `Estimated Shipping` are fixed costs from user settings. `Estimated Shipping` is only added if the `Shipping Included` flag is 'no'.

-   **`Profit`**:
    -   **Source**: `keepa_deals/business_calculations.py` -> `calculate_profit_and_margin()`
    -   **Logic**: A simple calculation: `List at` - `All-in Cost`.

-   **`Margin`**:
    -   **Source**: `keepa_deals/business_calculations.py` -> `calculate_profit_and_margin()`
    -   **Logic**: A simple calculation: `(Profit / List at) * 100`.

-   **`Min. Listing Price`**:
    -   **Source**: `keepa_deals/business_calculations.py` -> `calculate_min_listing_price()`
    -   **Logic**: Calculates a floor price for repricing software. The formula is:
        `All-in Cost` / (1 - `Default Markup %`). The markup is a user setting.

### Raw Keepa Stats Data

The following columns are generally direct extractions from the Keepa `stats` object, which contains arrays for current prices (`current`), 30-day averages (`avg30`), 365-day averages (`avg365`), etc. The value is looked up by a specific, fixed index in the corresponding array.

-   **Sales Rank Columns** (`Sales Rank - Current`, `Sales Rank - 30 days avg.`, etc.): Extracted from the `stats` object at index `3`.
-   **Amazon Price Columns** (`Amazon - Current`, `Amazon - 365 days avg.`, etc.): Extracted from the `stats` object at index `0`.

*** This is not a column we're currently showing in the web UI, however I'm realizing now that this Price is a useful indicator of what the market will bear, because it is almost certain that an FBA seller can never sell a book at a price that's higher than what Amazon sells it at. This Amazon Price could be useful in determining whether or not a suggested list price is reasonable or not. This would be complex 



-   **New Price Columns** (`New - Current`, `New - 365 days avg.`, etc.): Extracted from the `stats` object at index `1`.
-   **Used Price Columns** (`Used - Current`, `Used - 365 days avg.`, etc.): Extracted from the `stats` object at index `2`.
-   **Sub-Condition Columns** (`Used, like new - Current`, `Used, very good - 365 days avg.`, etc.): Extracted from the `stats` object at specific indices (`19` for Like New, `20` for Very Good, etc.).
-   **Buy Box Columns** (`Buy Box - Current`, `Buy Box - 365 days avg.`, etc.): Extracted from the `stats` object at specific indices (`18` for overall Buy Box, `32` for Used Buy Box).
-   **Offer Count Columns** (`New Offer Count - Current`, `Used Offer Count - 365 days avg.`, etc.): Sourced from both direct keys (`offerCountFBA`) and specific indices in the `stats` arrays (`11` for New count, `12` for Used count).

*Note: For a definitive mapping of every raw stat to its index, refer to the `get_stat_value` calls within the functions in `keepa_deals/stable_products.py`.*
