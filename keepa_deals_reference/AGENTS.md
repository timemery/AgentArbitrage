## Timestamp Handling Notes (from Task starting ~June 24-25, 2025)

When working with timestamp fields like 'last update' and 'last price change', the goal is to reflect the most recent relevant event as accurately as possible, aligning with user expectations from observing Keepa.com.

**For 'last_update':**
This field should represent the most recent time any significant data for the product/deal was updated by Keepa. It considers:
1.  `product_data['products'][0]['lastUpdate']` (general product data update from /product endpoint).
2.  `deal_object.get('lastUpdate')` (general deal data update from /deal endpoint).
3.  `product_data.get('stats', {}).get('lastOffersUpdate')` (when offers were last refreshed from /product endpoint stats).
The function should take the maximum valid (recent) timestamp from these three sources.

**For 'last_price_change' (specifically for Used items, excluding 'Acceptable'):**
This field aims to find the most recent price change for relevant used conditions.
1.  **Primary Source (`product_data.csv`):** Check historical data for 'USED' (`csv[2]`), 'USED_LIKE_NEW' (`csv[6]`), 'USED_VERY_GOOD' (`csv[7]`), and 'USED_GOOD' (`csv[8]`). Select the most recent valid timestamp from these.
2.  **Fallback Source (`deal_object.currentSince`):** If CSV data is insufficient, check `currentSince[2]` (Used), `currentSince[19]` (Used-LikeNew), `currentSince[20]` (Used-VeryGood), and `currentSince[21]` (Used-Good). Additionally, if `deal_object.current[14]` indicates the Buy Box is 'Used', also consider `currentSince[32]` (buyBoxUsedPrice timestamp). Select the most recent valid timestamp from this combined pool.

**General Timestamp Conversion:**
All Keepa minute timestamps should be converted to datetime objects using `KEEPA_EPOCH = datetime(2011, 1, 1)`, then localized from naive UTC to aware UTC (`timezone('UTC').localize(dt)`), and finally converted to 'America/Toronto' (`astimezone(TORONTO_TZ)`), formatted as '%Y-%m-%d %H:%M:%S'. Timestamps <= 100000 are generally considered invalid/too old.

## My Learnings from Investigating "Used, acceptable - Current" (Date: YYYY-MM-DD)

**Task Context:** I investigated discrepancies in the "Used, acceptable - Current" column of `Keepa_Deals_Export.csv`. It turned out some prices were incorrect due to historical fallback logic in the script.

**My Key Learnings & Principles:**

1.  **Dev Logs are Crucial Historical Records:**
    *   The `API_Dev_Log_v4.txt` was invaluable in understanding the evolution of the code and the rationale behind previous fixes. It helped me determine that the issue you described (incorrect prices due to fallbacks) had likely already been addressed.
    *   **Principle:** I've learned to always consult available development logs or historical documentation first. They can provide context, prevent redundant work, and reveal if a current problem is a regression or a known past issue.

2.  **Verify Current Code Against Problem Description:**
    *   You reported "fallbacks" as the cause of incorrect pricing. My analysis of the *current* `used_acceptable` function in `stable_products.py` showed that such fallback logic had been removed, and it was strictly using `stats.current[22]`.
    *   **Principle:** When investigating a bug, especially one described as "familiar," I now know to always compare the current state of the relevant code modules with the problem description. The problem might have been fixed in a previous iteration.

3.  **Distinguish Between Script Logic Errors and API Data Discrepancies:**
    *   The `used_acceptable` function now directly uses `stats.current[22]`. If price discrepancies persist for this field *after* confirming the code strictly uses this index, the issue likely lies with the data provided by the Keepa API for that specific index and ASIN, or a mismatch in interpretation between the API field and the website's display.
    *   **Principle:** I've learned to clearly differentiate between errors caused by the script's data processing/fallback logic and potential inconsistencies or specificities in the data received from external APIs. A fix for one might not address the other.

4.  **Simplify to Reduce Errors:**
    *   The original problem was caused by complex fallback logic pulling from "vaguely related fields." The fix, implemented prior to this task and confirmed during it, was to simplify the function to use a single, specific API data point (`stats.current[22]`)
    *   **Principle:** When dealing with API data, aiming for direct mapping to the most accurate known field, rather than implementing complex fallbacks, can often lead to more reliable and maintainable code. Fallbacks, if not carefully managed, can obscure data issues or introduce subtle errors.

5.  **Task-Specific Client Avoidance:**
    *   Your request specified avoiding the Keepa Python client. The existing solution (direct HTTP requests and JSON parsing) met this requirement.
    *   **Principle:** I will always adhere to specified constraints, such as avoiding particular libraries or clients, if feasible and clearly stated in the task.

**Outcome of this Investigation:**
*   I confirmed that the `used_acceptable` function in `stable_products.py` was already updated to use `stats.current[22]` without fallbacks, addressing the core issue.
*   No code changes were needed for this specific problem as the fix was pre-existing.
*   This investigation highlighted the importance of dev logs and careful analysis of the current codebase against historical issues.

## Task: FIX (second attempt) the “New, 3rd Party FBA - Lowest” Column (Solved June 2025)

**Core Problem:** The "New, 3rd Party FBA - Lowest" column in `Keepa_Deals_Export.csv` was showing incorrect data or hyphens.

**Key Learnings & Solutions:**

1.  **Understanding Keepa API Data Structures is Crucial:**
    *   `product['offers']`: This array contains information about *current* marketplace offers (up to the limit specified by the `&offers=` parameter in the API call). Each object within this array typically has an `offer.get('price')` field representing the current price of that specific offer.
    *   `product['stats']`: This object contains aggregated historical and current statistics. For specific price types (like 'New, 3rd Party FBA'), it has sub-arrays for `current`, `min`, `max`, `avg`, etc.
        *   `product.stats.min[INDEX][1]`: Provides the *historical minimum price* recorded by Keepa for the price type at `INDEX` (e.g., index 10 is for 'New, 3rd Party FBA') within the requested `stats` history period. The value is `[timestamp, price_in_cents]`, so `[1]` accesses the price.
        *   `product.stats.current[INDEX]`: Provides the *current price* for the price type at `INDEX`.
    *   `offer['offerCSV']` (within `product['offers']`): This field within an individual offer object in the `product['offers']` array is **not a simple array of current offer details**. Instead, it's a list of historical data points for *that specific offer's listing history* (often `[timestamp, price, shipping, stock, condition_code, ...]`, repeated). Using `offerCSV[0]` to get a current price is incorrect as it will likely be a timestamp.

2.  **Clarifying "Lowest":**
    *   The definition of "Lowest" (or any similar term) is critical. Does it mean lowest *currently active offer* or lowest *historical recorded price*?
    *   For this, "New, 3rd Party FBA - Lowest" was successfully implemented by targeting the *historical minimum* using `product.stats.min[10][1]`.
    *   If the goal were the *current lowest active offer*, iterating through `product.offers` and using `offer.get('price')` (while filtering for New, 3rd Party, FBA) would be the method, but this might not reflect true historical lows if that offer isn't currently active or among the top N offers retrieved.

3.  **Iterative Debugging & Log Analysis:**
    *   Detailed logging within data processing functions (showing inputs, intermediate values, and decisions) is invaluable for diagnosing issues, especially when dealing with complex API responses.
    *   Providing specific ASINs and their expected values, along with relevant log excerpts, significantly speeds up the debugging process.

4.  **API Parameter Impact (`fetch_product`):**
    *   The `offers=N` parameter in the `/product` API call limits the number of *current* offers returned in the `product.offers` array. It does not directly impact the `product.stats` data (like `stats.min`).
    *   The `stats=DAYS` parameter determines the historical window for aggregated statistics like `stats.min`.

5.  **Safe Data Access:**
    *   When accessing nested data from API responses (e.g., `product.get('stats', {}).get('min', [])`), always use safe access methods (like `.get()` with defaults) and check for the existence and type of data before trying to use it to prevent `KeyError` or `TypeError` exceptions. Check list lengths before accessing indices.

**Initial Missteps & Corrections:**

*   An early attempt incorrectly tried to use `offer['offerCSV'][0]` from within a `product['offers']` item as the current price, leading to errors because this field often contains a timestamp or historical data, not the current offer price directly.
*   Overly restrictive price validation (e.g., `MAX_REALISTIC_PRICE_CENTS`) can sometimes mask underlying issues if legitimate (though perhaps outlier) data is filtered out. It was helpful to temporarily remove these to diagnose the core problem.

**Final Successful Approach for 'New, 3rd Party FBA - Lowest':**

The solution was to modify `stable_products.py -> new_3rd_party_fba_lowest(product)` to use `product.stats.min[10][1]` to get the historical lowest price, ensuring safe access and correct formatting.

## Task: Fix "New, 3rd Party FBM - Current" Column (June 2025)

**Objective:** Ensure the "New, 3rd Party FBM - Current" column in `Keepa_Deals_Export.csv` accurately reflects the price shown on Keepa.com for this specific metric.

**Key Learnings & Conventions Established:**

1.  **Prioritize Direct `stats` Fields:**
    *   For aggregated price data like "New, 3rd Party FBM - Current (including shipping)", the Keepa API (via direct HTTP `product` endpoint with `stats` parameter) often provides this directly within the `product['stats']['current']` array at a specific index.
    *   Through analysis of logs and comparison with Keepa.com, `product['stats']['current'][7]` was identified as the direct source for "New, 3rd Party FBM - Current price, including shipping".
    *   **Convention:** When aiming to match a specific Keepa-displayed aggregate value, the first approach should be to identify and use the corresponding index in `product['stats']['current']` (or other relevant `stats` arrays like `avg30`, `avg90`, etc.). These fields represent Keepa's own calculated values.

2.  **Strict Data Sourcing for Specific Columns:**
    *   To ensure a column *exactly* matches a specific Keepa field (e.g., "New, 3rd Party FBM - Current"), the script should *only* use the identified direct source (like `stats.current[7]`).
    *   If this direct source is invalid (e.g., -1, null, or unavailable), the column should output "-" rather than falling back to parsing general offers. This prevents populating the column with data that, while potentially related (e.g., a general lowest FBM offer), isn't what Keepa designates for that specific field, thus maintaining data integrity for that column's definition.

3.  **Offer Parsing as a Fallback (for broader "lowest price" type columns):**
    *   For columns intended to find the *absolute lowest* offer of a certain type (e.g., "New, 3rd Party FBA - Lowest"), iterating through the `product['offers']` array is necessary.
    *   **`offerCSV` Complexity:** The `offerCSV` field within an individual offer object is a flat list representing historical data points for that offer. Each data point can have a variable number of elements (not always simple `[timestamp, price, shipping]` triplets). The most recent *actual live price and shipping* for an offer are typically found by looking at the latest entries in `offerCSV` or by using the direct `offer['price']` and `offer['shippingCost']` fields.
    *   **Parsing `offerCSV`:** If parsing `offerCSV` for current price/shipping:
        *   The last elements often represent the latest state. For example, if an entry is `[ts, price, shipping]`, then `offer_csv[-2]` might be price and `offer_csv[-1]` shipping for the most recent data point in that array.
        *   This requires careful handling of array length and potential variations in the number of elements per `offerCSV` entry.
    *   Direct `offer['price']` and `offer['shippingCost']` can serve as fallbacks or primary sources if `offerCSV` is not used or proves too complex for reliable current-price extraction for a given offer type.

4.  **Identifying Offer Characteristics:**
    *   **Condition:** `offer.get('condition') == 1` is a reliable check for "New" items.
    *   **FBM vs. FBA:** `offer.get('isFBA', False)` (checking for `False` for FBM, `True` for FBA) is generally used. The default to `False` if the key is missing helps catch FBM offers where the flag might not be explicit.
    *   **Seller ID:** `offer.get('sellerId')` can be used to exclude Amazon (`ATVPDKIKX0DER`) for 3rd party offers.

5.  **Logging for Debugging:**
    *   Detailed logging within data processing functions is crucial, especially when dealing with complex API responses.
    *   Logs should indicate:
        *   The source of the data being used (e.g., "from stats.current[X]", "from offerCSV", "from direct offer.price").
        *   Key intermediate values (e.g., extracted price, shipping before calculation).
        *   Reasons for offers being included or excluded from consideration.
        *   The final value chosen for a field.

6.  **API Request Parameters:**
    *   The `fetch_product` function uses `offers=100` and `stats=365` (or other day counts). The `stats` parameter is necessary to populate `product['stats']`. The `offers` parameter controls how many individual current marketplace offers are returned in `product['offers']`.

**Implication for Future Tasks:**
When a new column is required, or an existing one is incorrect:
*   First, determine if Keepa provides this as a direct aggregated field (likely in `stats.current` or similar). This is the preferred method for matching specific Keepa-displayed values.
*   If not, or if the goal is to find the "absolute lowest of all available offers" of a type, then careful parsing of `product['offers']` is needed, paying attention to `condition`, `isFBA`, `sellerId`, and robustly extracting price + shipping (likely from `offerCSV`'s latest entry or direct `price`/`shippingCost` fields).
*   Always verify against Keepa.com, and use detailed logging to trace the script's logic.

## Character Encoding and Symbol Compatibility (Task: Percent Down 365, YYYY-MM-DD)

**Learning:** When implementing features that involve special characters or symbols (e.g., arrows like ⇧⇩ for indicating price changes), always consider cross-platform compatibility and potential rendering issues in different environments (terminals, CSV viewers, etc.).

**Problem:** Initial implementation of "Percent Down 365" used Unicode arrows (U+21E7 ⇧, U+21E9 ⇩). These did not render correctly in the user's local testing environment, appearing as garbled characters (e.g., ‚á©).

**Solution & Principle:**
*   Switched to universally compatible ASCII symbols: "+" for an increase (price above average) and "-" for a decrease (price below average). No symbol is used for a 0% difference.
*   **Principle:** Prioritize widely supported character sets (like ASCII or well-tested UTF-8 subsets) for textual indicators unless specific rich text rendering is guaranteed and tested across all target environments. If special symbols are desired, ensure they are tested for compatibility or provide simpler fallbacks.

## CSV Data Interpretation Notes

*   **Date Formatting in Viewing Software:** Be aware that spreadsheet programs (like Microsoft Excel, Google Sheets, etc.) often automatically interpret columns containing date-like strings (e.g., "YYYY-MM-DD", "YYYY-MM") as dates. Their default display formatting for these dates might differ from the raw string in the CSV file (e.g., "1985-06" in the CSV might be displayed as "Jun-85" in Excel). Always verify the raw CSV content in a text editor if precise string formatting is critical and appears different in a spreadsheet.

## Keepa API `stats` Object Insights (Specifically `avg...` arrays)

When working with aggregated statistical arrays from the Keepa API `/product` endpoint (e.g., `stats.current`, `stats.avg30`, `stats.avg90`, `stats.avg365`), the indices for different price types can be specific and sometimes require empirical verification if not explicitly documented for every array type.

**Learnings from "Buy Box - 365 days avg." Investigation (YYYY-MM-DD):**

*   **Initial Assumption:** Index `10` in `stats.avg365` was initially thought to be for "Buy Box - 365 days avg."
*   **Verification:** User feedback and direct log analysis of the `stats_raw.avg365` array for ASIN `0262611317` revealed:
    *   `avg365[10]` corresponded to "New, 3rd Party FBA - 365 days avg." (value: `11460` or $114.60).
    *   `avg365[18]` corresponded to "Buy Box - 365 days avg." (value: `6916` or $69.16). This matched user observations on Keepa.com.

**Key Takeaway:**
*   While there are common patterns for indices (e.g., 0 for AMAZON, 1 for NEW, 2 for USED), specific types like "Buy Box Shipping" or nuanced FBA/FBM averages can have distinct indices.
*   For `avg...` arrays (like `avg365`), **index 18** was confirmed to provide the "Buy Box (including shipping) Average" for the respective period.
*   Always verify assumptions about indices by:
    1.  Consulting any available explicit Keepa documentation for that specific array.
    2.  If unclear, inspect the raw JSON response from the API (specifically the `stats` object and its arrays like `current`, `avg30`, `avg90`, `avg365`) for a known ASIN where the desired data point is visible on Keepa.com. This allows mapping the observed value to its position in the array.
    3.  Cross-reference with field names provided in the `csv` field of the product data, as these often map directly to indices (e.g., `csv[18]` might be Buy Box price history).

**Example `avg365` array structure snippet for ASIN `0262611317`:**
`[-1, 9021 (Amazon), 2742 (Used), ..., 9257 (New FBM), ..., 11460 (New FBA), ..., 6916 (Buy Box Shipping), ...]`
*(Note: This is a simplified representation; always refer to the full array for accurate indexing.)*

## Keepa API `stats` Object Insights (Specifically `avg...` arrays)

When working with aggregated statistical arrays from the Keepa API `/product` endpoint (e.g., `stats.current`, `stats.avg30`, `stats.avg90`, `stats.avg365`), the indices for different price types can be specific and sometimes require empirical verification if not explicitly documented for every array type.

**Learnings from Investigations (YYYY-MM-DD for Buy Box Used Avg):**

*   **Buy Box (Overall) Averages:**
    *   For `avg...` arrays (like `avg365`), **index 18** was confirmed to provide the "Buy Box (including shipping) Average" for the respective period.
*   **Buy Box Used - Current:**
    *   `stats.current[32]` is used for the "Buy Box Used - Current" price.
*   **Buy Box Used - 365 days avg. (Confirmed <YYYY-MM-DD>):**
    *   **Index 32** in `stats.avg365` is confirmed to correspond to "Buy Box Used - 365 days avg.". This was verified through local testing after hypothesizing based on the index for the current value.

**Key Takeaway for `avg...` arrays:**
*   While there are common patterns for indices (e.g., 0 for AMAZON, 1 for NEW, 2 for USED), specific types like "Buy Box Shipping" or nuanced FBA/FBM averages, and particularly *used* buy box averages, can have distinct indices (e.g., `stats.avg365[32]` for Buy Box Used average).
*   Always verify assumptions about indices by:
    1.  Consulting any available explicit Keepa documentation for that specific array.
    2.  If unclear, inspect the raw JSON response from the API (specifically the `stats` object and its arrays) for a known ASIN where the desired data point is visible on Keepa.com.
    3.  Cross-reference with field names provided in the `csv` field of the product data, as these often map directly to indices.
    4.  Confirm with local testing, especially when an index is hypothesized.

---
## General Notes for Agents:

- **Function Placement & Imports:**
    - Be mindful of the distinction between `stable_products.py`, `stable_deals.py`, and `stable_calculations.py`.
    - Product-specific data getters (e.g., current price, average price of a specific condition, product attributes) generally reside in `stable_products.py`.
    - Deal-specific logic (e.g., `deal_found`, `last_update` related to a deal event) generally resides in `stable_deals.py`.
    - Complex calculations derived from product/deal data often go into `stable_calculations.py`.
    - When adding or modifying function mappings in `field_mappings.py`, double-check that functions are imported from their correct source file to avoid `ImportError` issues. An `ImportError` traceback pointing to an import from `stable_deals` for a function actually in `stable_products` (or vice-versa) has been a recurring theme.
---

## AGENTS.md - Troubleshooting `ImportError: cannot import name 'FUNCTION_LIST' from 'field_mappings'`

When encountering `ImportError: cannot import name 'FUNCTION_LIST' from 'field_mappings'`, consider the following common causes, especially after adding new functions/fields:

1.  **Syntax Error in `field_mappings.py` itself:** Even a small syntax error can prevent the file from being parsed, meaning `FUNCTION_LIST` is never defined.
2.  **Syntax Error in an Imported Module:** An error in `stable_products.py`, `stable_deals.py`, or `stable_calculations.py` can prevent `field_mappings.py` from successfully importing a function from it, which can sometimes cascade into `FUNCTION_LIST` not being properly defined or exported.
3.  **Incorrect Import Source:** Ensure the new function (e.g., `my_new_function`) is imported from the correct source file within `field_mappings.py`. For example:
    *   `from stable_products import my_new_function` (if it's in `stable_products.py`)
    *   NOT `from stable_deals import my_new_function` (if it's actually in `stable_products.py`). This has been a recurring issue.
4.  **Circular Dependencies:** While less common with the current structure, a circular import (e.g., `stable_products` trying to import something from `field_mappings` which imports from `stable_products`) can cause this.
5.  **File Path/Environment Issues:** Ensure Python can find all the .py files correctly. (Usually less of an issue with all files in the same directory).

**Diagnostic Steps:**
*   Carefully review the recently modified files (`field_mappings.py` and the file where the new function was added) for syntax errors.
*   Temporarily comment out the new function import and its usage in `FUNCTION_LIST` within `field_mappings.py`. If the `ImportError` disappears, the issue is related to the new function.
*   If necessary, temporarily comment out the new function definition in its source file (e.g., `stable_products.py`) as well, to isolate whether the definition itself or its usage in `field_mappings.py` is the problem.

*   **Used Condition Averages (`avg...` arrays):**
    *   `stats.avg365[2]` is for "Used - 365 days avg." (overall used).
    *   `stats.avg365[19]` is for "Used, like new - 365 days avg.".
    *   `stats.avg365[20]` is for "Used, very good - 365 days avg.".
    *   `stats.avg365[21]` is confirmed for "Used, good - 365 days avg." (YYYY-MM-DD).
    *   (Index for "Used, acceptable - 365 days avg." would likely be `stats.avg365[22]` if needed, following the pattern from `stats.current[22]`.)
    *   "New Offer Count - Current": Sum of `product['stats'].get('offerCountFBA', 0)` and `product['stats'].get('offerCountFBM', 0)`.
    *   "Used Offer Count - Current": Calculated as `product['stats'].get('totalOfferCount', 0) - (sum of new FBA & FBM counts)`.
    *   "New Offer Count - 365 days avg.": `product['stats']['avg365'][11]` (corresponds to historical `csv[11]` for `COUNT_NEW`).
    *   "Used Offer Count - 365 days avg.": `product['stats']['avg365'][12]` (corresponds to historical `csv[12]` for `COUNT_USED`).

### Keepa API Data Structure Notes

*   **Accessing Price/Rank Statistics:** Product statistics (current prices, average prices over various periods like 30, 90, 365 days, min/max prices) are generally found within the `product['stats']` object.
    *   Current values are typically in `product['stats']['current'][index]`.
    *   Average values for a period `D` (e.g., 30, 90, 365) are in `product['stats']['avgD'][index]`.
    *   The `index` within these arrays corresponds to a specific price type or rank. For example:
        *   `[0]`: Amazon price
        *   `[1]`: New overall price
        *   `[2]`: Used overall price
        *   `[3]`: Sales Rank
        *   `[4]`: List Price (current - may vary for averages)
        *   `[7]`: New, 3rd Party FBM (current & averages)
        *   `[10]`: New, 3rd Party FBA (current & averages)
        *   `[18]`: Buy Box Shipping (current & averages)
        *   `[19]`: Used, Like New (current & averages)
        *   `[20]`: Used, Very Good (current & averages)
        *   `[21]`: Used, Good (current & averages)
        *   `[22]`: Used, Acceptable (current & averages)
        *   `[32]`: Buy Box Used (current & averages - verify specific index for averages if needed)
    *   Always verify the exact index for less common fields or if a direct field like `product['stats']['buyBoxPrice']` is not sufficient or available for averages. The `Keepa_Documentation-official.md` might list some, but others are found through empirical testing and observing API responses (see `debug_log.txt` for `stats_raw` entries).
*   **Field Naming Consistency:** When adding new functions for fields like "Condition - X days avg.", ensure the function name in `stable_products.py` (e.g., `used_acceptable_365_days_avg`) and its import/usage in `field_mappings.py` are consistent.


*   **Offer Counts (Current & Average):**
    *   **New Offer Count - Current**: Derived by summing `product['stats'].get('offerCountFBA', 0)` and `product['stats'].get('offerCountFBM', 0)`. These are direct keys in the `stats` object.
    *   **Used Offer Count - Current**: Calculated as `product['stats'].get('totalOfferCount', 0) - ( new_offer_count_fba + new_offer_count_fbm )`. Requires careful handling if `totalOfferCount` is missing or less than the sum of new offers.
    *   **New Offer Count - 365 days avg.**: Found at `product['stats']['avg365'][11]`. This index corresponds to the historical data type `COUNT_NEW` (new offer count history, often seen as `csv[11]` in `product.csv`).
    *   **Used Offer Count - 365 days avg.**: Found at `product['stats']['avg365'][12]`. This index corresponds to the historical data type `COUNT_USED` (used offer count history, often seen as `csv[12]` in `product.csv`).
    *   *Note:* The indices `stats.current[5]`, `stats.current[6]`, `stats.avg365[5]`, and `stats.avg365[6]` were found to be incorrect for these specific offer counts and likely represent other data.

    ## Keepa API Product Data Structure Notes

*   **FBA Pick & Pack Fee:** To retrieve the FBA Pick & Pack Fee for a product, access the `product_data` object (JSON response from the `/product` endpoint) as follows:
    *   The fee is stored within a dictionary named `fbaFees`.
    *   Inside the `fbaFees` dictionary, the specific fee is under the key `pickAndPackFee`.
    *   The value is provided in **cents**.
    *   Example path: `product_data.get('fbaFees', {}).get('pickAndPackFee')`
    *   Ensure to handle cases where `fbaFees` or `pickAndPackFee` might be missing or `None`.

## Keepa API Product Data Structure Notes

*   **FBA Pick & Pack Fee:** To retrieve the FBA Pick & Pack Fee for a product, access the `product_data` object (JSON response from the `/product` endpoint) as follows:
    *   The fee is stored within a dictionary named `fbaFees`.
    *   Inside the `fbaFees` dictionary, the specific fee is under the key `pickAndPackFee`.
    *   The value is provided in **cents**.
    *   Example path: `product_data.get('fbaFees', {}).get('pickAndPackFee')`
    *   Ensure to handle cases where `fbaFees` or `pickAndPackFee` might be missing or `None`.

*   **Referral Fee Percentage (Added YYYY-MM-DD):**
    *   The Keepa API `/product` endpoint response may contain referral fee percentage information at the root of the `product_data` object.
    *   Prioritize the field `product_data.get('referralFeePercentage')` as it typically provides a precise decimal value (e.g., 14.99).
    *   A less precise, potentially rounded integer version might be available at `product_data.get('referralFeePercent')` (e.g., 15).
    *   If these direct fields are not present, referral fee information might also be speculatively found nested under an `fbaFees` object, similar to other fees (e.g., `product_data.get('fbaFees', {}).get('referralFeePercentage')` or `product_data.get('fbaFees', {}).get('referralFee', {}).get('percent')`).
    *   When implementing, check for the more precise `referralFeePercentage` first, then fall back to other known or speculative locations. The value is a direct percentage (e.g., 14.99 for 14.99%).

## Keepa API Interaction Notes

### Rate Limiting and Headers

*   **No Server-Side Rate Limit Headers**: As of [mention date or task reference if possible, e.g., July 2024 analysis / Task X], it has been confirmed that the Keepa API **does not** return standard rate limit headers (e.g., `x-rate-limit-limit`, `x-rate-limit-remaining`, `x-rate-limit-reset`) in its responses.
*   **Implications for Scripting**:
    *   The `rate_limit_info` dictionary (or similar structures in scripts attempting to parse these headers) will consistently reflect `{'limit': None, 'remaining': None, 'reset': None}` (or equivalent empty/null values).
    *   Any client-side logic designed for dynamic rate limit adjustments based on these specific headers will be **ineffective** as it will not receive the necessary data from the API.
    *   Strategies for avoiding 429 "Too Many Requests" errors must rely on conservative fixed delays between API calls (e.g., `MIN_TIME_SINCE_LAST_CALL_SECONDS`) and potentially client-side quota estimations if Keepa publishes separate, non-header-based usage limits.
*   **Current Strategy**: The `Keepa_Deals.py` script has been modified to use a fixed delay between calls and does not attempt to parse or react to these non-existent headers for dynamic rate adjustments.

## Keepa API - Potential for Batch Product Queries

**Date of Research:** July 5, 2025 (via Grok, based on user query)

**Finding:** Research indicates that the Keepa API **officially supports batch querying of product details for up to 100 ASINs in a single call**.

**Methods Identified:**
1.  **Direct HTTP Request:** The standard `product` endpoint (currently used for single ASINs in `Keepa_Deals.py`) reportedly accepts a comma-separated list of up to 100 ASINs in the `asin` parameter (e.g., `&asin=ASIN1,ASIN2,ASIN3...`).
2.  **Python `keepa` Library:** The official `keepa` Python library has an `api.query(asins_list, ...)` method designed for batch requests.

**Potential Benefits if Implemented:**
*   Significant reduction in the number of API calls (e.g., from N calls to N/100 calls).
*   Reduced network overhead.
*   Potential for faster overall data retrieval if the rate limits for batch calls are favorable.
*   Reports suggest token cost might be 1 token per ASIN within the batch, potentially more efficient than the current 2 tokens per ASIN for individual product detail fetches.

**Open Questions / Areas for Verification (as of July 5, 2025):**
*   **HTTP Batch Request - Token Cost Confirmation:** What is the exact token cost per ASIN when using the comma-separated list in the HTTP `product` endpoint? (Is it indeed 1 token per ASIN?)
*   **HTTP Batch Request - Response Structure:** What is the exact JSON structure of the response when multiple ASINs are requested via the HTTP `product` endpoint? (e.g., is it `{"products": [product1, product2, ...]}`?)
*   **HTTP Batch Request - Rate Limiting:** How are batch HTTP requests treated by Keepa's rate limiting? Does one batch call count as one request, or does it count as N requests internally for throttling purposes? What delay would be safe between batch calls?

**Current Status (as of this note):**
*   `Keepa_Deals.py` currently makes individual API calls for each ASIN's product details.
*   Implementation of batch querying is pending further verification of the above questions and successful testing of the current individual-call fixed-delay strategy.

## Keepa API - Batch Product Query Details (Follow-up Research)

**Date of Research:** July 5, 2025 (via Grok, second query)
**Source:** Primarily Keepa API documentation and community forums, focusing on direct HTTP implications and Python library behavior.

**Key Verifications & New Details for Batch Queries:**

1.  **Token Cost Breakdown:**
    *   The base cost for an ASIN in a batch is **1 token**.
    *   **Crucially, additional parameters like `offers` (2 extra tokens/ASIN) or `buybox` still apply their costs *per ASIN within the batch*.** There's no reduction in token cost per ASIN for the *same data parameters* when batching versus individual calls. The primary benefit is reduced HTTP overhead and potentially different call rate treatment.
    *   Example: A request for 100 ASINs with parameters that cost X tokens per ASIN individually will still cost `100 * X` tokens in a batch (if X is the sum of base + parameter costs).

2.  **Response Structure (Confirmed):**
    *   The JSON response for a batch query includes a top-level `products` array. Each element in the array is a dictionary for an ASIN, containing details like `asin`, `title`, `data`, etc.
    *   The response may also contain top-level keys like `tokensLeft` and `refillIn` (milliseconds), which could provide direct feedback on token status if present in direct HTTP calls.
    *   Invalid ASINs in a batch return no data for that ASIN but still consume their token share.

3.  **Rate Limiting Behavior & Safe Frequency:**
    *   A batch request (e.g., for 100 ASINs) is treated as a **single HTTP request** by Keepa.
    *   The primary rate limit is the overall token quota and its refill rate (typically 5% of max tokens per hour).
    *   Explicit per-second/minute call limits are not documented, but 429 errors (`NOT_ENOUGH_TOKEN`) occur if the token bucket is empty.
    *   A **safe frequency** suggested for batch calls (especially when using the Python library's `wait=True` parameter, which handles some throttling) is around **1 to 2 batch requests per minute**. This implies a delay of 30-60 seconds *between batch calls* could be a good starting point.
    *   Standard advice is to use exponential backoff if 429s are encountered.

**Implications for `Keepa_Deals.py` Strategy:**
*   The major speed benefit of batching comes from processing up to 100 ASINs with the overhead of a single HTTP call, and potentially allowing a faster *effective* ASIN processing rate (e.g., 100 ASINs every 30-60 seconds vs. 1 ASIN every 60 seconds).
*   The total number of tokens consumed for the same dataset and parameters will likely remain similar to individual calls.
*   If direct HTTP batch calls also return `tokensLeft` and `refillIn`, this could allow for a much more accurate client-side token management and dynamic delay system than previously thought possible.
*   The `MIN_TIME_SINCE_LAST_CALL_SECONDS` in `Keepa_Deals.py` would need to be re-evaluated to be the delay *between batch calls*.

**Next Steps (Post-Current Test):**
1.  Confirm the outcome of the current test (individual calls with 60s delay).
2.  If proceeding with batch implementation:
    *   Prioritize verifying the exact token cost per ASIN for the *specific parameters* we use (`stats`, `offers`, `stock`, `buybox`, etc.) when called in a batch via direct HTTP.
    *   Verify if `tokensLeft` and `refillIn` are present in the direct HTTP batch response.
    *   Plan a phased implementation, starting with a new function for batch fetching via direct HTTP.

---
## Keepa API Token Costs & Batching Strategy (Learnings as of July 8, 2025 - Revised with Official Docs)

**Token Cost Primary Source: `tokensConsumed` Field**
*   The Keepa API (including `/product` and `/deal` endpoints) returns a `tokensConsumed` field in its JSON response. This field indicates the *actual* number of tokens consumed by that specific API call.
*   **Crucially, this applies even to 429 error responses if they return a JSON body.**
*   `Keepa_Deals.py` has been refactored to prioritize parsing and using this `tokensConsumed` value for all token deductions, making local accounting much more accurate.

**`/deal` Endpoint (e.g., `fetch_deals_for_deals`):**
*   Cost: **1 token per request/page**. This is because the `buybox` parameter in the `selection` JSON defaults to `false` when omitted.

**`/product` Endpoint (Batch ASIN Details Fetch):**
*   The cost is **variable per ASIN** and primarily driven by the `offers` parameter when used.
*   **Base Cost Waved with `offers`:** When `&offers=` is used with a positive integer, the default "1 token per ASIN" base cost for the product itself is **waived**.
*   **`&offers=N` Cost:**
    *   **6 tokens for every found offer page per product.** An offer page contains up to 10 offers.
    *   Example: If `offers=100` is requested for an ASIN that has 25 actual offers, this requires 3 offer pages (10, 10, 5). Cost for offers for this ASIN = `3 * 6 = 18 tokens`.
*   **`&buybox=1` Cost:**
    *   **0 tokens (ignored)** when `&offers=` is also used, as the `offers` parameter already provides all Buy Box data.
*   **`&stats=DAYS` Cost (e.g., `&stats=365`):**
    *   **0 tokens.** Stats are derived from existing historical data.
*   **`&history=1` (default to include history):**
    *   **0 tokens.**
*   **`&rating=1` Cost:**
    *   **0 or 1 token per product**, consumed only if Keepa's rating/review data for the product was updated recently (<14 days).
*   **`&stock=1` Cost (used with `&offers=`):**
    *   **0 or 2 tokens per product**, consumed only if Keepa's stock data for the product was updated recently (<7 days).

*   **Pre-Call Estimation:** Since the actual cost (from `tokensConsumed`) is only known *after* a call, `Keepa_Deals.py` uses `ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH` (e.g., 15 tokens) for pre-call checks to decide if it should wait for refills. This is an estimate, and the actual deducted amount comes from `tokensConsumed`.

**Batch Processing & Rate Limiting Strategy (`Keepa_Deals.py`):**
*   **Batch Size:** `MAX_ASINS_PER_BATCH = 50` (configurable, API max is 100).
*   **Inter-Call Delay:** `MIN_TIME_SINCE_LAST_CALL_SECONDS = 60` between API calls.
*   **429 Error Handling:**
    *   Retries the *same batch* up to 2 more times (3 total attempts).
    *   Exponential backoff pauses: 15 minutes after 1st failure, 30 minutes after 2nd.
    *   If a 429 response includes `tokensConsumed > 0`, those tokens ARE deducted.
*   **Token Refill Simulation:** Now based on **5 tokens per minute**, checked every 60 seconds, to more closely match Keepa's actual refill rate.

## Agent Performance Notes & Learnings
- (Add this section if it doesn't exist)

### Token Cost Estimation (Keepa_Deals.py)
- **Updated: 2025-07-11**
- The `ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH` constant is critical for efficient script operation.
- This value should be periodically reviewed and adjusted based on analysis of `tokensConsumed` data from full runs, as actual API costs can vary.
- Do not assume a low value; use data from `debug_log.txt` from substantial runs to inform this constant.

## Debugging Persistent or Recurring Errors

**Date of Learning:** July 12, 2025

**Issue:** A `TypeError` (incorrect number of arguments for `deal_found`) persisted across multiple test runs, even after a fix was thought to have been applied by removing a duplicated code block.

**Root Cause:** The initial fix attempt was incomplete. The erroneous code block was either misidentified, or the edit was not applied correctly, causing the bug to remain in the script.

**Key Learning & Principle:**

1.  **Verify Fixes with Targeted Log Analysis:** When a specific error is reported in logs (e.g., a `TypeError` at a specific line or for a specific function), do not assume a fix is successful until a new test run's log is analyzed to confirm the *absence* of that specific error message. A general "it seems to work now" is insufficient.
2.  **Trust the Latest Log:** The latest log is the ground truth. If an error that was supposedly fixed reappears in a new log, it means the fix was not effective. The investigation must restart by re-examining the code for the same error pattern, rather than assuming a new, different cause.
3.  **Searching is a Key Tool:** Using precise searches to find specific error messages or ASINs in large log files is an essential and effective debugging strategy. When a narrow search returns no results, broaden the search (e.g., to just the ASIN) to confirm if the item was processed at all before concluding the specific error is gone.
