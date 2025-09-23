1. # Request Seller Information

   **Token Cost:** 1 per requested seller

   This API retrieves the [seller object](https://discuss.keepa.com/t/seller-object/791) using the seller ID. If a seller is not found in our database, no tokens will be consumed, and no data will be provided.

   ------

   ## Query

   ```php-template
   /seller?key=<yourAccessKey>&domain=<domainId>&seller=<sellerId>
   ```

   ### Parameters

   - `<yourAccessKey>`: Your private API key.

   - `<domainId>`: Integer value for the Amazon locale you want to access.

     **Valid values:**

     | Domain ID | Locale |
     | :-------- | :----- |
     | **1**     | com    |
     | **2**     | co.uk  |
     | **3**     | de     |
     | **4**     | fr     |
     | **5**     | co.jp  |
     | **6**     | ca     |
     | **8**     | it     |
     | **9**     | es     |
     | **10**    | in     |
     | **11**    | com.mx |

   - `<sellerId>`: The seller ID of the merchant you want to request. For batch requests, provide a comma-separated list of seller IDs (up to **100**). The seller ID is part of the offer object and can also be found on Amazon’s seller profile pages in the `seller` parameter of the URL.

     **Example:**

     - Seller ID: **A2L77EE7U53NWQ**

       Amazon.com Warehouse Deals: [Link](https://www.amazon.com/sp?marketplaceID=ATVPDKIKX0DER&seller=A2L77EE7U53NWQ)

   ------

   ## Optional Parameters for Requesting the Storefront

   ### About the Storefront

   The storefront of a seller is a list of items the merchant is offering on Amazon. We provide ASINs that are currently listed, as well as ASINs this merchant has listed within the past 7 days.

   #### Collection Through Our Database

   - We collect seller ASINs daily by scanning our database for products sold by the seller.
   - Popular ASINs and competitive offers are more likely to be included.
   - Utilizing our vast offers database allows us to collect more ASINs than Amazon’s storefront page displays.
   - However, the fewer items a seller is listing, the less likely we have recently tracked any of their offers.
   - The ASIN lists may be incomplete, and data may be outdated by a few days.
   - If the storefront is requested via the `storefront` parameter, this list will always be included in the seller object unless we have no data or the seller has no items.

   #### Collection From Amazon

   - To complement the database list, you can request a collection of ASINs from the seller’s storefront page on Amazon.
   - Amazon limits this to **29** storefront pages, which equals **462** ASINs.
   - Additionally, we can identify the total number of products sold by this seller as listed on the seller’s storefront page.
   - To trigger this additional collection, the `update` parameter must be specified as well.

   **Note:** Regardless of the collection method, we cannot guarantee to provide a complete storefront list.

   - A storefront ASIN list can contain up to **100,000** ASINs, sorted by the last time we verified an active offer by the seller (freshest first).
   - Each ASIN in the list comes with a last-seen timestamp.

   **Important:** Seller ID batch requests are **not allowed** when requesting the storefront and will cause an error if submitted.

   ------

   ## Optional Parameters

   - `storefront`: Include additional information about the items the seller is listing.
   - `update`: Force a new collection from Amazon if the last update is older than specified hours.

   ------

   ### `storefront`

   **Additional Token Cost:** 9

   Valid values: **0** (false), **1** (true)

   If specified and set to `1`, the seller object will contain additional information about the items the seller is listing on Amazon, including:

   - A list of ASINs (`asinList`)
   - Last-seen timestamps for each ASIN (`asinListLastSeen`)
   - Total number of items the seller has listed (`totalStorefrontAsinsCSV`)

   If no data is available, no additional tokens will be consumed.

   - The ASIN list can contain up to **100,000** items.
   - Using the `storefront` parameter does **not** trigger any new data collection and does **not** increase the processing time of the request.
   - The response may be larger in size due to the additional data.
   - The total storefront ASIN count will not be updated; only historical data will be provided (when available).

   **Example:**

   - `&storefront=1`

   **Total Token Cost:**

   - If storefront data is available and contains at least 2 ASINs: **1** (seller object) + **9** (storefront data) = **10** tokens.
   - Otherwise: **1** token for the seller object.

   ------

   ### `update`

   **Total Request Token Cost:** 50

   Positive integer value. If the last live data collection from the Amazon storefront page is older than `<update>` hours, force a new collection. Use the `update` parameter in conjunction with the `storefront` parameter.

   **Token Cost Breakdown:**

   - **50** tokens if collection is triggered and successful.
   - **10** tokens if fresh collection is not necessary.
   - **1** token if collection failed (existing storefront data will be provided) or if no storefront data is available and only seller data is provided.

   **Using this parameter, you can:**

   - **Retrieve data from Amazon:** Get a storefront ASIN list containing up to **464** ASINs, in addition to ASINs collected from our database.
   - **Force a refresh:** Always retrieve live data by setting the value to **0**.
   - **Retrieve the total number of listings:** The `totalStorefrontAsinsCSV` field of the seller object will be updated.

   **Note:**

   - The storefront data collection requires additional processing time, varying between **0.5** and **12** seconds, depending on how many listings the seller has.
   - Parallel requests for multiple sellers may not be fully executed in parallel and can increase total processing time.
   - We advise making sequential `update` and `storefront` requests whenever possible.

   **Example:**

   - `&update=48` (Only trigger an update if the last storefront collection is older than 48 hours)

   ------

   ## Response

   A `sellers` field containing a map of [seller objects](https://discuss.keepa.com/t/seller-object/791). Within this map:

   - Each **key** corresponds to a `sellerId`.
   - Each **value** is associated with a seller object.
   - If no sellers are found, this map will be empty.
   - If any specified `sellerId` is invalid, an error will be indicated within the error field.



   # Product Search

   **Token Cost:** 10 per result page (up to 10 results)

   Search for Amazon products using keywords, returning up to **100** results per search term. The results are in the same order as a search on Amazon, excluding sponsored content. By default, the product search response contains the product objects of the found products.

   ------

   ## Query

   ```php-template
   /search?key=<yourAccessKey>&domain=<domainId>&type=product&term=<searchTerm>
   ```

   ### Parameters

   - `<yourAccessKey>`: Your private API key.

   - `<domainId>`: Integer value for the Amazon locale you want to access.

     **Valid values:**

     | Domain ID | Locale |
     | :-------- | :----- |
     | **1**     | com    |
     | **2**     | co.uk  |
     | **3**     | de     |
     | **4**     | fr     |
     | **5**     | co.jp  |
     | **6**     | ca     |
     | **8**     | it     |
     | **9**     | es     |
     | **10**    | in     |
     | **11**    | com.mx |

   - `<searchTerm>`: The term you want to search for. Should be [URL encoded](https://en.wikipedia.org/wiki/Percent-encoding).

   ------

   ## Optional Parameters

   - **`asins-only`**: If provided and set to `1`, only the ASINs of the found products will be provided instead of the full product objects.

     **Example:** `&asins-only=1`

   - **`page`**: Integer value between **0** and **9**. Each search result page provides up to **10** results. To retrieve more results, iterate the `page` parameter while keeping all other parameters identical. Start with `page=0` and stop when the response contains fewer than 10 results or when you reach `page=9`, which is the limit.

     - **Note:** When not using the `page` parameter, the first **40** results will be returned.

     **Example:** `&page=0`

   - **`stats`**: No extra token cost. If specified, the product object will include a `stats` field with quick access to current prices, min/max prices, and weighted mean values.

     You can provide the `stats` parameter in two forms:

     - **Last x days**: A positive integer value representing the number of last days to calculate stats for.

       **Example:** `&stats=180` (stats for the last 180 days)

     - **Interval**: Specify a date range for the stats calculation using two timestamps (Unix epoch time in milliseconds) or two date strings (ISO8601 format, with or without time in UTC).

       **Examples:**

       - `&stats=2015-10-20,2015-12-24` (from October 20 to December 24, 2015)
       - `&stats=1445299200000,1450915200000` (Unix epoch time in milliseconds)

     **Note:** If there is insufficient historical data for a price type, the actual interval of the weighted mean calculation may be shorter than specified. All data provided via the `stats` field are calculated using the product object’s `csv` history field; no new data is provided through this parameter.

   - **`update`**

     **Additional Token Cost:** 0 or 1 per found product

     Positive integer value. If the product’s last update is older than `<update>` hours, force a refresh. The default value the API uses is **1** hour.

     **Usage:**

     - **Speed up requests:** If up-to-date data is not required, use a higher value than **1** hour. No extra token cost.
     - **Always retrieve live data:** Use the value **0**. If our last update for the product was less than 1 hour ago, this consumes **1 extra token** per product.

     **Example:** `&update=48` (only trigger an update if the product’s last update is older than 48 hours)

   - **`history`**

     No extra token cost. Boolean value (`0` = false, `1` = true). If specified and set to `0`, the product object will not include the `csv` field. Use this to reduce response size and improve processing time if you do not need the historical data.

     **Example:** `&history=0`

   - **`rating`**

     Up to **1** extra token per found product (**maximum of 5 additional tokens per search**). Boolean value (`0` = false, `1` = true). If specified and set to `1`, the product object will include our existing `RATING` and `COUNT_REVIEWS` history in the `csv` field.

     - The extra token will only be consumed if our last update to both data points is less than **14** days ago.
     - Using this parameter does not trigger an update to these fields; it only provides access to existing data if available.
     - If you need up-to-date data, you have to use the `offers` parameter of a separate product request.
     - Use this if you need access to the rating data, which may be outdated, but do not need any other data fields provided through the `offers` parameter to save tokens and speed up the request.

     **Example:** `&rating=1` (include rating and review count data in the `csv` field)

   ------

   ## Response

   An ordered array of [product objects](https://discuss.keepa.com/t/product-object/116) in the `products` field, or an ordered string array of ASINs in the `asinList` field (if the `asins-only` parameter was used).





# Browsing Deals

**Token Cost:** 5 per request providing up to 150 deals

By accessing our [deals](https://keepa.com/#!deals), you can find products that recently changed and match your search criteria. A single request will return a maximum of **150** deals. A query can provide up to **10,000** ASINs using paging. We recommend trying out our [deals page](https://keepa.com/#!deals) first to familiarize yourself with the options and results before reading this documentation.

**Note:** Our deals only provide products that were updated within the last **12 hours**.

------

## Query

You can choose between an HTTP GET or POST request.

### GET Format

```php-template
/deal?key=<yourAccessKey>&selection=<queryJSON>
```

- `<yourAccessKey>`: Your private API key.
- `<queryJSON>`: The query JSON contains all request parameters. It must be URL-encoded if the GET format is used.

**Tip:** To quickly get a valid `queryJSON`, there is a link on the [deals page](https://keepa.com/#!deals) below the filters that generates this JSON for the current selection.

### POST Format

```bash
/deal?key=<yourAccessKey>
```

- `<yourAccessKey>`: Your private API key.
- **POST payload**: Must contain a `<queryJSON>`.

------

## `queryJSON` Format

```json
{
  "page": Integer,
  "domainId": Integer,
  "excludeCategories": [Long],
  "includeCategories": [Long],
  "priceTypes": [Integer],
  "deltaRange": [Integer],
  "deltaPercentRange": [Integer],
  "deltaLastRange": [Integer],
  "salesRankRange": [Integer],
  "currentRange": [Integer],
  "minRating": Integer,
  "isLowest": Boolean,
  "isLowest90": Boolean,
  "isLowestOffer": Boolean,
  "isHighest": Boolean,
  "isOutOfStock": Boolean,
  "isBackInStock": Boolean,
  "titleSearch": String,
  "isRangeEnabled": Boolean,
  "isFilterEnabled": Boolean,
  "hasReviews": Boolean,
  "filterErotic": Boolean,
  "singleVariation": Boolean,
  "isRisers": Boolean,
  "isPrimeExclusive": Boolean,
  "mustHaveAmazonOffer": Boolean,
  "mustNotHaveAmazonOffer": Boolean,
  "warehouseConditions": [Integer],
  "material": [String],
  "type": [String],
  "manufacturer": [String],
  "brand": [String],
  "productGroup": [String],
  "model": [String],
  "color": [String],
  "size": [String],
  "unitType": [String],
  "scent": [String],
  "itemForm": [String],
  "pattern": [String],
  "style": [String],
  "itemTypeKeyword": [String],
  "targetAudienceKeyword": [String],
  "edition": [String],
  "format": [String],
  "author": [String],
  "binding": [String],
  "languages": [String],
  "brandStoreName": [String],
  "brandStoreUrlName": [String],
  "websiteDisplayGroup": [String],
  "websiteDisplayGroupName": [String],
  "salesRankDisplayGroup": [String],
  "sortType": Integer,
  "dateRange": Integer,
}
```

### Parameters

- **`page`**

  - Most deal queries have more than 150 results (maximum page size).
  - To browse all deals found by a query (up to the limit of **10,000**), iterate the `page` parameter while keeping all other parameters identical.
  - Start with `page=0` and stop when the response contains fewer than 150 results.

  **Example:**

  ```json
  "page": 0
  ```

- **`domainId`**

  - The `domainId` of the Amazon locale to retrieve deals for. Not optional.

  **Possible values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- **`priceTypes`**

  - Determines the deal type. Not optional: exactly price type must be specified.
  - Though it is an integer array, it can contain **only one entry**. Multiple types per query are not supported.

  **Possible values:**

  | Value  | Price Type                                                |
  | :----- | :-------------------------------------------------------- |
  | **0**  | AMAZON: Amazon price                                      |
  | **1**  | NEW: Marketplace New price                                |
  | **2**  | USED: Marketplace Used price                              |
  | **3**  | SALES: Sales Rank                                         |
  | **5**  | COLLECTIBLE: Collectible price                            |
  | **6**  | REFURBISHED: Refurbished price                            |
  | **7**  | NEW_FBM_SHIPPING: New FBM with shipping                   |
  | **8**  | LIGHTNING_DEAL: Lightning Deal price                      |
  | **9**  | WAREHOUSE: Amazon Warehouse price                         |
  | **10** | NEW_FBA: New FBA price                                    |
  | **18** | BUY_BOX_SHIPPING: New Buy Box with shipping               |
  | **19** | USED_NEW_SHIPPING: Used - Like New with shipping          |
  | **20** | USED_VERY_GOOD_SHIPPING: Used - Very Good with shipping   |
  | **21** | USED_GOOD_SHIPPING: Used - Good with shipping             |
  | **22** | USED_ACCEPTABLE_SHIPPING: Used - Acceptable with shipping |
  | **32** | BUY_BOX_USED_SHIPPING: Used Buy Box with shipping         |
  | **33** | PRIME_EXCL: Prime Exclusive Price                         |

  **Example:**

  ```json
  "priceTypes": [0]
  ```

- **`dateRange`**

  - Our deals are divided into different sets, determined by the time interval in which the product changed.
  - The shorter the interval, the more recent the change, which is good for significant price drops but may miss slow incremental drops.

  **Possible values:**

  | Value | Interval                |
  | :---- | :---------------------- |
  | **0** | Day (last 24 hours)     |
  | **1** | Week (last 7 days)      |
  | **2** | Month (last 31 days)    |
  | **3** | 3 Months (last 90 days) |

  **Example:**

  ```json
  "dateRange": 0
  ```

------

### Filter Options

- **`isFilterEnabled`**

  - Switch to enable the filter options.

  **Example:**

  ```json
  "isFilterEnabled": true
  ```

- **`excludeCategories`**

  - Used to exclude products listed in these categories.
  - If it’s a subcategory, the product must be **directly** listed in this category.
  - Products in child categories of the specified ones will not be excluded unless it’s a root category.
  - Array with up to **500** [category node IDs](https://discuss.keepa.com/t/category-object/115).

  **Example:**

  ```json
  "excludeCategories": [77028031, 186606]
  ```

- **`includeCategories`**

  - Used to include only products listed in these categories.
  - Same rules as `excludeCategories`.

  **Example:**

  ```json
  "includeCategories": [3010075031, 12950651, 355007011]
  ```

- **`minRating`**

  - Limit to products with a minimum rating.
  - A rating is an integer from **0** to **50** (e.g., 45 = 4.5 stars).
  - If `-1`, the filter is inactive.

  **Example:**

  ```json
  "minRating": 20  // Minimum rating of 2 stars
  ```

- **`isLowest`**

  - Include only products for which the specified price type is at its lowest value (since tracking began).

  **Example:**

  ```json
  "isLowest": true
  ```

- **`isLowest90`**

  - Include only products for which the specified price type is at its lowest value in the past 90 days.

  **Example:**

  ```json
  "isLowest90": true
  ```

- **`isLowestOffer`**

  - Include only products if the selected price type is the lowest of all New offers (applicable to Amazon and Marketplace New).

  **Example:**

  ```json
  "isLowestOffer": true
  ```

- **`isHighest`**

  - Include only products for which the specified price type is at its highest value (since tracking began).

  **Example:**

  ```json
  "isHighest": true
  ```

- **`isOutOfStock`**

  - Include only products that were available to order within the last 24 hours and are now out of stock.

  **Example:**

  ```json
  "isOutOfStock": true
  ```

- **`isBackInStock`**

  - Include only products that were previously out of stock and have returned to stock within the last 24 hours.

  **Example:**

  ```json
  "isBackInStock": true
  ```

- **`hasReviews`**

  - If `true`, exclude all products with no reviews.
  - If `false`, the filter is inactive.

  **Example:**

  ```json
  "hasReviews": false
  ```

- **`filterErotic`**

  - Exclude all products listed as adult items.

  **Example:**

  ```json
  "filterErotic": false
  ```

- **`singleVariation`**

  - Provide only a single variation if multiple match the query. The one provided is randomly selected.

  **Example:**

  ```json
  "singleVariation": true
  ```

- **`isRisers`**

  - Include only products whose price has been rising over the chosen `dateRange` interval.

  **Example:**

  ```json
  "isRisers": true
  ```

- **`isPrimeExclusive`**

  - Include only products flagged as Prime Exclusive.

  **Example:**

  ```json
  "isPrimeExclusive": true
  ```

- **`mustHaveAmazonOffer`**

  - Include only products that currently have an offer sold and fulfilled by Amazon.

  **Example:**

  ```json
  "mustHaveAmazonOffer": true
  ```

- **`mustNotHaveAmazonOffer`**

  - Include only products that currently have no offer sold and fulfilled by Amazon.

  **Example:**

  ```json
  "mustNotHaveAmazonOffer": true
  ```

- **`warehouseConditions`**

  - Include only products available under the specified Amazon Warehouse conditions. Use an array of integer condition codes (e.g., 1 = New, 2 = Used - Like New, 3 = Used - Very Good, 24 = Used - Good, 5 = Used - Acceptable).

  **Example:**

  ```json
  "warehouseConditions": [1, 2]
  ```

- **`material`**

  - Include only products made of the specified material (e.g., “cotton”).

  **Example:**

  ```json
  "material": ["cotton"]
  ```

- **`type`**

  - Include only products matching the specified type (e.g., “shirt”, “dress”).

- **`manufacturer`**

  - Include only products from the specified manufacturer.

- **`brand`**

  - Include only products from the specified brand.

- **`productGroup`**

  - Include only products in the specified Amazon product group (e.g., “home”, “book”).

- **`model`**

  - Include only products matching the specified model identifier.

- **`color`**

  - Include only products matching the specified color attribute.

- **`size`**

  - Include only products matching the specified size (e.g., “small" “one size”).

- **`unitType`**

  - Include only products with the specified unit type (e.g., “count”, “ounce”).

- **`scent`**

  - Include only products with the specified scent (e.g., “lavender”, “citrus”).

- **`itemForm`**

  - Include only products matching the specified item form (e.g., “liquid”, “sheet”).

- **`pattern`**

  - Include only products matching the specified pattern (e.g., “striped”, “solid”).

- **`style`**

  - Include only products matching the specified style attribute (e.g., “modern”, “vintage”).

- **`itemTypeKeyword`**

  - Include only products matching the specified item type keyword (custom search term, e.g., “books”, “prints”).

- **`targetAudienceKeyword`**

  - Include only products targeting the specified audience (e.g., “kids”, “professional”).

- **`edition`**

  - Include only products matching the specified edition (e.g., “first edition”, “standard edition”).

- **`format`**

  - Include only products in the specified format (e.g., “kindle ebook”, “import”, “dvd”).

- **`author`**

  - Include only products by the specified author (applicable to books, music, etc.).

- **`binding`**

  - Include only products with the specified binding type (e.g., “paperback”).

- **`languages`**

  - Include only products available in the specified languages. Use an array of language names.

- **`brandStoreName`**

  - Include only products sold under the specified brand store name on Amazon.

- **`brandStoreUrlName`**

  - Include only products sold under the specified URL-friendly brand store identifier.

- **`websiteDisplayGroup`**

  - Include only products in the specified website display group

- **`websiteDisplayGroupName`**

  - Include only products in the specified website display group name (a more user-friendly label).

- **`salesRankDisplayGroup`**

  - Include only products belonging to the specified sales rank display group (e.g., “fashion_display_on_website”).

------

### Range Options

All range options are integer arrays with two entries: `[min, max]`.

- **`isRangeEnabled`**

  - Switch to enable the range options.

  **Example:**

  ```json
  "isRangeEnabled": true
  ```

- **`currentRange`**

  - Limit the range of the current value of the price type.

  **Example:**

  ```json
  "currentRange": [105, 50000]  // Min price $1.05, max price $500
  ```

- **`deltaRange`**

  - Limit the range of the difference between the weighted average value and the current value over the chosen `dateRange` interval.

  **Example:**

  ```json
  "deltaRange": [0, 999]  // Max difference of $9.99
  ```

- **`deltaPercentRange`**

  - Same as `deltaRange`, but in percent.
  - Minimum percent is **10%**; for Sales Rank, it is **80%**.

  **Example:**

  ```json
  "deltaPercentRange": [30, 80]  // Between 30% and 80%
  ```

- **`deltaLastRange`**

  - Limit the range of the absolute difference between the previous value and the current one.

  **Example:**

  ```json
  "deltaLastRange": [100, 500]  // Last change between $1 and $5 price decrease
  ```

- **`salesRankRange`**

  - Limit the Sales Rank range of the product.
  - Identical to `currentRange` if the price type is set to Sales Rank.
  - If you want to keep the upper bound open, you can specify `-1` (which translates to the maximum integer value).
  - **Important:** Once this range option is used, all products with no Sales Rank will be excluded. Set it to `null` or leave it out to not use it.

  **Examples:**

  ```json
  "salesRankRange": [0, 5000]     // Sales Rank between 0 and 5000
  "salesRankRange": [5000, -1]    // Sales Rank higher than 5000
  ```

------

### Search and Sort Options

- **`titleSearch`**

  - Select deals by a keyword-based product title search.
  - The search is case-insensitive and supports up to **50** keywords.
  - If multiple keywords are specified (separated by a space), all must match.

  **Example:**

  ```json
  "titleSearch": "samsung galaxy"  // Matches products with both "samsung" AND "galaxy" in the title
  ```

- **`sortType`**

  - Determines the sort order of the retrieved deals.
  - To invert the sort order, use negative values.

  **Possible values:**

  | Value | Sort By          | Order                               |
  | :---- | :--------------- | :---------------------------------- |
  | **1** | Deal age         | Newest deals first (not invertible) |
  | **2** | Absolute delta   | Highest delta to lowest             |
  | **3** | Sales Rank       | Lowest rank to highest              |
  | **4** | Percentage delta | Highest percent to lowest           |

------

## Example Query

```json
{
  "page": 0,
  "domainId": 1,
  "excludeCategories": [1064954, 11091801],
  "includeCategories": [16310101],
  "priceTypes": [0],
  "deltaRange": [0, 10000],
  "deltaPercentRange": [20, 100],
  "deltaLastRange": null,
  "salesRankRange": [0, 40000],
  "currentRange": [500, 40000],
  "minRating": -1,
  "isLowest": false,
  "isLowestOffer": false,
  "isOutOfStock": false,
  "titleSearch": null,
  "isRangeEnabled": true,
  "isFilterEnabled": false,
  "filterErotic": true,
  "hasReviews": false,
  "singleVariation": true,
  "sortType": 4,
  "dateRange": 1
}
```

------

## Notes

### Lightning Deals, Prime Exclusive, and Warehouse Deals

- The `deltaLast`, `delta`, `deltaPercent` entries for these price types are calculated with the Amazon or New price as the reference price (instead of the same price type’s previous price).

------

## Response

The response contains a `deals` field with the following content:

```json
{
  "dr": [deal objects],
  "categoryIds": [Long],
  "categoryNames": [String],
  "categoryCount": [Integer]
}
```

### Response Fields

- **`dr`**
  - Ordered array of all [deal objects](https://discuss.keepa.com/t/deal-object/412) matching your query.
- **`categoryIds`**
  - Includes all root `categoryIds` of the matched deal products. The returned categories will update based on any filters used in your query, except for category filters. If category filters are applied, they will not affect the returned category information.
- **`categoryNames`**
  - Includes all root category names of the matched deal products. The returned category names will update based on any filters used, other than category filters. If category filters are used, they will not affect the returned category information.
- **`categoryCount`**
  - Indicates the number of deal products found in each respective root category. This count updates based on any filters used except for category filters. Applying category filters will not affect the returned category information.

**Note:**

- Each deal product is listed in a single root category.
- The arrays `categoryIds`, `categoryNames`, and `categoryCount` are related by their index positions.
- If the root category of a product cannot be determined, it will be listed in the category with the name `"?"` and the ID `9223372036854775807`.

**Example of One Index:**

- **ID:** `165793011`
- **Name:** `"Toys & Games"`
- **Count:** `40`

For more information about categories, visit the [category object](https://discuss.keepa.com/t/category-object/115) page.





# Most Rated Seller List

**Token Cost:** 50

Retrieve a list of Seller IDs for the most rated Amazon marketplace sellers.

- **Ordering**: Lists are ordered starting with the most rated seller.
- **Updates**: Lists are updated daily and contain up to **100,000** seller IDs.
- **Availability**: Lists are not available for Amazon Brazil.

------

## Query

```php-template
/topseller?key=<yourAccessKey>&domain=<domainId>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access.

  **Valid values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

------

## Response

The response contains an ordered string array `sellerIdList` field containing [seller IDs](https://discuss.keepa.com/t/seller-object/791).

- You can use the [Request Seller Information](https://discuss.keepa.com/t/request-seller-information/790) API to look up more information about a seller.

**Example Response:**

```json
{
  "sellerIdList": [
    "A1PA6795UKMFR9",
    "A1RKKUPIHCS9HS",
    "A3KYXGYZHZZIOF",
    "...",
    "ANOTHER_SELLER_ID"
  ]
}
```



# Browsing Deals

**Token Cost:** 5 per request providing up to 150 deals

By accessing our [deals](https://keepa.com/#!deals), you can find products that recently changed and match your search criteria. A single request will return a maximum of **150** deals. A query can provide up to **10,000** ASINs using paging. We recommend trying out our [deals page](https://keepa.com/#!deals) first to familiarize yourself with the options and results before reading this documentation.

**Note:** Our deals only provide products that were updated within the last **12 hours**.

------

## Query

You can choose between an HTTP GET or POST request.

### GET Format

```php-template
/deal?key=<yourAccessKey>&selection=<queryJSON>
```

- `<yourAccessKey>`: Your private API key.
- `<queryJSON>`: The query JSON contains all request parameters. It must be URL-encoded if the GET format is used.

**Tip:** To quickly get a valid `queryJSON`, there is a link on the [deals page](https://keepa.com/#!deals) below the filters that generates this JSON for the current selection.

### POST Format

```bash
/deal?key=<yourAccessKey>
```

- `<yourAccessKey>`: Your private API key.
- **POST payload**: Must contain a `<queryJSON>`.

## `queryJSON` Format

```
{
  "page": Integer,
  "domainId": Integer,
  "excludeCategories": [Long],
  "includeCategories": [Long],
  "priceTypes": [Integer],
  "deltaRange": [Integer],
  "deltaPercentRange": [Integer],
  "deltaLastRange": [Integer],
  "salesRankRange": [Integer],
  "currentRange": [Integer],
  "minRating": Integer,
  "isLowest": Boolean,
  "isLowest90": Boolean,
  "isLowestOffer": Boolean,
  "isHighest": Boolean,
  "isOutOfStock": Boolean,
  "isBackInStock": Boolean,
  "titleSearch": String,
  "isRangeEnabled": Boolean,
  "isFilterEnabled": Boolean,
  "hasReviews": Boolean,
  "filterErotic": Boolean,
  "singleVariation": Boolean,
  "isRisers": Boolean,
  "isPrimeExclusive": Boolean,
  "mustHaveAmazonOffer": Boolean,
  "mustNotHaveAmazonOffer": Boolean,
  "warehouseConditions": [Integer],
  "material": [String],
  "type": [String],
  "manufacturer": [String],
  "brand": [String],
  "productGroup": [String],
  "model": [String],
  "color": [String],
  "size": [String],
  "unitType": [String],
  "scent": [String],
  "itemForm": [String],
  "pattern": [String],
  "style": [String],
  "itemTypeKeyword": [String],
  "targetAudienceKeyword": [String],
  "edition": [String],
  "format": [String],
  "author": [String],
  "binding": [String],
  "languages": [String],
  "brandStoreName": [String],
  "brandStoreUrlName": [String],
  "websiteDisplayGroup": [String],
  "websiteDisplayGroupName": [String],
  "salesRankDisplayGroup": [String],
  "sortType": Integer,
  "dateRange": Integer,
}
```



### Parameters

- **`page`**

  - Most deal queries have more than 150 results (maximum page size).
  - To browse all deals found by a query (up to the limit of **10,000**), iterate the `page` parameter while keeping all other parameters identical.
  - Start with `page=0` and stop when the response contains fewer than 150 results.

  **Example:**

  ```json
  "page": 0
  ```

- **`domainId`**

  - The `domainId` of the Amazon locale to retrieve deals for. Not optional.

  **Possible values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- **`priceTypes`**

  - Determines the deal type. Not optional: exactly price type must be specified.
  - Though it is an integer array, it can contain **only one entry**. Multiple types per query are not supported.

  **Possible values:**

  | Value  | Price Type                                                |
  | :----- | :-------------------------------------------------------- |
  | **0**  | AMAZON: Amazon price                                      |
  | **1**  | NEW: Marketplace New price                                |
  | **2**  | USED: Marketplace Used price                              |
  | **3**  | SALES: Sales Rank                                         |
  | **5**  | COLLECTIBLE: Collectible price                            |
  | **6**  | REFURBISHED: Refurbished price                            |
  | **7**  | NEW_FBM_SHIPPING: New FBM with shipping                   |
  | **8**  | LIGHTNING_DEAL: Lightning Deal price                      |
  | **9**  | WAREHOUSE: Amazon Warehouse price                         |
  | **10** | NEW_FBA: New FBA price                                    |
  | **18** | BUY_BOX_SHIPPING: New Buy Box with shipping               |
  | **19** | USED_NEW_SHIPPING: Used - Like New with shipping          |
  | **20** | USED_VERY_GOOD_SHIPPING: Used - Very Good with shipping   |
  | **21** | USED_GOOD_SHIPPING: Used - Good with shipping             |
  | **22** | USED_ACCEPTABLE_SHIPPING: Used - Acceptable with shipping |
  | **32** | BUY_BOX_USED_SHIPPING: Used Buy Box with shipping         |
  | **33** | PRIME_EXCL: Prime Exclusive Price                         |

  **Example:**

  ```json
  "priceTypes": [0]
  ```

- **`dateRange`**

  - Our deals are divided into different sets, determined by the time interval in which the product changed.
  - The shorter the interval, the more recent the change, which is good for significant price drops but may miss slow incremental drops.

  **Possible values:**

  | Value | Interval                |
  | :---- | :---------------------- |
  | **0** | Day (last 24 hours)     |
  | **1** | Week (last 7 days)      |
  | **2** | Month (last 31 days)    |
  | **3** | 3 Months (last 90 days) |

  **Example:**

  ```json
  "dateRange": 0
  ```

------

### Filter Options

- **`isFilterEnabled`**

  - Switch to enable the filter options.

  **Example:**

  ```json
  "isFilterEnabled": true
  ```

- **`excludeCategories`**

  - Used to exclude products listed in these categories.
  - If it’s a subcategory, the product must be **directly** listed in this category.
  - Products in child categories of the specified ones will not be excluded unless it’s a root category.
  - Array with up to **500** [category node IDs](https://discuss.keepa.com/t/category-object/115).

  **Example:**

  ```json
  "excludeCategories": [77028031, 186606]
  ```

- **`includeCategories`**

  - Used to include only products listed in these categories.
  - Same rules as `excludeCategories`.

  **Example:**

  ```json
  "includeCategories": [3010075031, 12950651, 355007011]
  ```

- **`minRating`**

  - Limit to products with a minimum rating.
  - A rating is an integer from **0** to **50** (e.g., 45 = 4.5 stars).
  - If `-1`, the filter is inactive.

  **Example:**

  ```json
  "minRating": 20  // Minimum rating of 2 stars
  ```

- **`isLowest`**

  - Include only products for which the specified price type is at its lowest value (since tracking began).

  **Example:**

  ```json
  "isLowest": true
  ```

- **`isLowest90`**

  - Include only products for which the specified price type is at its lowest value in the past 90 days.

  **Example:**

  ```json
  "isLowest90": true
  ```

- **`isLowestOffer`**

  - Include only products if the selected price type is the lowest of all New offers (applicable to Amazon and Marketplace New).

  **Example:**

  ```json
  "isLowestOffer": true
  ```

- **`isHighest`**

  - Include only products for which the specified price type is at its highest value (since tracking began).

  **Example:**

  ```json
  "isHighest": true
  ```

- **`isOutOfStock`**

  - Include only products that were available to order within the last 24 hours and are now out of stock.

  **Example:**

  ```json
  "isOutOfStock": true
  ```

- **`isBackInStock`**

  - Include only products that were previously out of stock and have returned to stock within the last 24 hours.

  **Example:**

  ```json
  "isBackInStock": true
  ```

- **`hasReviews`**

  - If `true`, exclude all products with no reviews.
  - If `false`, the filter is inactive.

  **Example:**

  ```json
  "hasReviews": false
  ```

- **`filterErotic`**

  - Exclude all products listed as adult items.

  **Example:**

  ```json
  "filterErotic": false
  ```

- **`singleVariation`**

  - Provide only a single variation if multiple match the query. The one provided is randomly selected.

  **Example:**

  ```json
  "singleVariation": true
  ```

- **`isRisers`**

  - Include only products whose price has been rising over the chosen `dateRange` interval.

  **Example:**

  ```json
  "isRisers": true
  ```

- **`isPrimeExclusive`**

  - Include only products flagged as Prime Exclusive.

  **Example:**

  ```json
  "isPrimeExclusive": true
  ```

- **`mustHaveAmazonOffer`**

  - Include only products that currently have an offer sold and fulfilled by Amazon.

  **Example:**

  ```json
  "mustHaveAmazonOffer": true
  ```

- **`mustNotHaveAmazonOffer`**

  - Include only products that currently have no offer sold and fulfilled by Amazon.

  **Example:**

  ```json
  "mustNotHaveAmazonOffer": true
  ```

- **`warehouseConditions`**

  - Include only products available under the specified Amazon Warehouse conditions. Use an array of integer condition codes (e.g., 1 = New, 2 = Used - Like New, 3 = Used - Very Good, 24 = Used - Good, 5 = Used - Acceptable).

  **Example:**

  ```json
  "warehouseConditions": [1, 2]
  ```

- **`material`**

  - Include only products made of the specified material (e.g., “cotton”).

  **Example:**

  ```json
  "material": ["cotton"]
  ```

- **`type`**

  - Include only products matching the specified type (e.g., “shirt”, “dress”).

- **`manufacturer`**

  - Include only products from the specified manufacturer.

- **`brand`**

  - Include only products from the specified brand.

- **`productGroup`**

  - Include only products in the specified Amazon product group (e.g., “home”, “book”).

- **`model`**

  - Include only products matching the specified model identifier.

- **`color`**

  - Include only products matching the specified color attribute.

- **`size`**

  - Include only products matching the specified size (e.g., “small" “one size”).

- **`unitType`**

  - Include only products with the specified unit type (e.g., “count”, “ounce”).

- **`scent`**

  - Include only products with the specified scent (e.g., “lavender”, “citrus”).

- **`itemForm`**

  - Include only products matching the specified item form (e.g., “liquid”, “sheet”).

- **`pattern`**

  - Include only products matching the specified pattern (e.g., “striped”, “solid”).

- **`style`**

  - Include only products matching the specified style attribute (e.g., “modern”, “vintage”).

- **`itemTypeKeyword`**

  - Include only products matching the specified item type keyword (custom search term, e.g., “books”, “prints”).

- **`targetAudienceKeyword`**

  - Include only products targeting the specified audience (e.g., “kids”, “professional”).

- **`edition`**

  - Include only products matching the specified edition (e.g., “first edition”, “standard edition”).

- **`format`**

  - Include only products in the specified format (e.g., “kindle ebook”, “import”, “dvd”).

- **`author`**

  - Include only products by the specified author (applicable to books, music, etc.).

- **`binding`**

  - Include only products with the specified binding type (e.g., “paperback”).

- **`languages`**

  - Include only products available in the specified languages. Use an array of language names.

- **`brandStoreName`**

  - Include only products sold under the specified brand store name on Amazon.

- **`brandStoreUrlName`**

  - Include only products sold under the specified URL-friendly brand store identifier.

- **`websiteDisplayGroup`**

  - Include only products in the specified website display group

- **`websiteDisplayGroupName`**

  - Include only products in the specified website display group name (a more user-friendly label).

- **`salesRankDisplayGroup`**

  - Include only products belonging to the specified sales rank display group (e.g., “fashion_display_on_website”).

------

### Range Options

All range options are integer arrays with two entries: `[min, max]`.

- **`isRangeEnabled`**

  - Switch to enable the range options.

  **Example:**

  ```json
  "isRangeEnabled": true
  ```

- **`currentRange`**

  - Limit the range of the current value of the price type.

  **Example:**

  ```json
  "currentRange": [105, 50000]  // Min price $1.05, max price $500
  ```

- **`deltaRange`**

  - Limit the range of the difference between the weighted average value and the current value over the chosen `dateRange` interval.

  **Example:**

  ```json
  "deltaRange": [0, 999]  // Max difference of $9.99
  ```

- **`deltaPercentRange`**

  - Same as `deltaRange`, but in percent.
  - Minimum percent is **10%**; for Sales Rank, it is **80%**.

  **Example:**

  ```json
  "deltaPercentRange": [30, 80]  // Between 30% and 80%
  ```

- **`deltaLastRange`**

  - Limit the range of the absolute difference between the previous value and the current one.

  **Example:**

  ```json
  "deltaLastRange": [100, 500]  // Last change between $1 and $5 price decrease
  ```

- **`salesRankRange`**

  - Limit the Sales Rank range of the product.
  - Identical to `currentRange` if the price type is set to Sales Rank.
  - If you want to keep the upper bound open, you can specify `-1` (which translates to the maximum integer value).
  - **Important:** Once this range option is used, all products with no Sales Rank will be excluded. Set it to `null` or leave it out to not use it.

  **Examples:**

  ```json
  "salesRankRange": [0, 5000]     // Sales Rank between 0 and 5000
  "salesRankRange": [5000, -1]    // Sales Rank higher than 5000
  ```

------

### Search and Sort Options

- **`titleSearch`**

  - Select deals by a keyword-based product title search.
  - The search is case-insensitive and supports up to **50** keywords.
  - If multiple keywords are specified (separated by a space), all must match.

  **Example:**

  ```json
  "titleSearch": "samsung galaxy"  // Matches products with both "samsung" AND "galaxy" in the title
  ```

- **`sortType`**

  - Determines the sort order of the retrieved deals.
  - To invert the sort order, use negative values.

  **Possible values:**

  | Value | Sort By          | Order                               |
  | :---- | :--------------- | :---------------------------------- |
  | **1** | Deal age         | Newest deals first (not invertible) |
  | **2** | Absolute delta   | Highest delta to lowest             |
  | **3** | Sales Rank       | Lowest rank to highest              |
  | **4** | Percentage delta | Highest percent to lowest           |

------

## Example Query

{
  "page": 0,
  "domainId": 1,
  "excludeCategories": [1064954, 11091801],
  "includeCategories": [16310101],
  "priceTypes": [0],
  "deltaRange": [0, 10000],
  "deltaPercentRange": [20, 100],
  "deltaLastRange": null,
  "salesRankRange": [0, 40000],
  "currentRange": [500, 40000],
  "minRating": -1,
  "isLowest": false,
  "isLowestOffer": false,
  "isOutOfStock": false,
  "titleSearch": null,
  "isRangeEnabled": true,
  "isFilterEnabled": false,
  "filterErotic": true,
  "hasReviews": false,
  "singleVariation": true,
  "sortType": 4,
  "dateRange": 1
}

## Notes

### Lightning Deals, Prime Exclusive, and Warehouse Deals

- The `deltaLast`, `delta`, `deltaPercent` entries for these price types are calculated with the Amazon or New price as the reference price (instead of the same price type’s previous price).

------

## Response

The response contains a `deals` field with the following content:

```json
{
  "dr": [deal objects],
  "categoryIds": [Long],
  "categoryNames": [String],
  "categoryCount": [Integer]
}
```

### Response Fields

- **`dr`**
  - Ordered array of all [deal objects](https://discuss.keepa.com/t/deal-object/412) matching your query.
- **`categoryIds`**
  - Includes all root `categoryIds` of the matched deal products. The returned categories will update based on any filters used in your query, except for category filters. If category filters are applied, they will not affect the returned category information.
- **`categoryNames`**
  - Includes all root category names of the matched deal products. The returned category names will update based on any filters used, other than category filters. If category filters are used, they will not affect the returned category information.
- **`categoryCount`**
  - Indicates the number of deal products found in each respective root category. This count updates based on any filters used except for category filters. Applying category filters will not affect the returned category information.

**Note:**

- Each deal product is listed in a single root category.
- The arrays `categoryIds`, `categoryNames`, and `categoryCount` are related by their index positions.
- If the root category of a product cannot be determined, it will be listed in the category with the name `"?"` and the ID `9223372036854775807`.

**Example of One Index:**

- **ID:** `165793011`
- **Name:** `"Toys & Games"`
- **Count:** `40`

# Category Lookup

**Token Cost:** 1

Retrieve [category objects](https://discuss.keepa.com/t/category-object/115) and optionally their parent tree using a category ID.

**Note:** We cannot provide any data for promotional categories (e.g., Launchpad).

------

## Query

```php-template
/category?key=<yourAccessKey>&domain=<domainId>&category=<categoryId>&parents=<includeParents>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access.

  **Valid values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- `<categoryId>`: The category node ID of the category you want to request.

  - For batch requests, use a comma-separated list of IDs (up to **10**). **Token cost remains the same.**
  - Alternatively, you can specify the value **0** to retrieve a list of all root categories.

- `<includeParents>`: Whether or not to include the category tree for each category.

  - Valid values:
    - **`1`**: Include parent categories.
    - **`0`**: Do not include parent categories.

------

## Response

*Identical to the [Category Search](https://discuss.keepa.com/t/category-searches/114/1).*

The response contains:

- A `categories` field with all found [category objects](https://discuss.keepa.com/t/category-object/115).
- If the `parents` parameter was set to `1`, a `categoryParents` field with all category objects found on the way to the tree’s root.

You can construct a category tree by traversing the parents.

Both fields are maps in the format `<categoryId, categoryObject>`:

```json
{
  "<categoryId>": categoryObject,
  "<categoryId2>": categoryObject,
  ...
}
```



# Search for Categories

**Token Cost:** 1

Search for Amazon category names. Retrieves up to 50 matching [category objects](https://discuss.keepa.com/t/category-object/115).

------

## Query

```php-template
/search?key=<yourAccessKey>&domain=<domainId>&type=category&term=<searchTerm>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access.

  **Valid values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- `<searchTerm>`: The term you want to search for. Should be [URL encoded](https://en.wikipedia.org/wiki/Percent-encoding). Multiple space-separated keywords are possible, and all provided keywords must match. The minimum length of a keyword is **3** characters.

------

## Response

*Identical to the [Category Lookup](https://discuss.keepa.com/t/requesting-categories/113).*

The response contains a `categories` field with all matching [category objects](https://discuss.keepa.com/t/category-object/115) in the format:

```json
{
  "<categoryId>": categoryObject,
  "<categoryId2>": categoryObject,
  ...
}
```



# Lightning Deals

**Token Cost:** 1 per lightning deal or 500 to request all

This API request provides access to current lightning deals. You can specify an ASIN to inquire about a specific deal (token cost: **1**), or request the complete list for an overview (token cost: **500**). Please note that this covers lightning deals exclusively, excluding other types of deals.

The comprehensive list includes lightning deals from the past **four days**, encompassing both active and expired deals.

------

## Query

```php-template
/lightningdeal?key=<yourAccessKey>&domain=<domainId>&asin=<ASIN>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access.

  **Valid values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- `<ASIN>`: The ASIN of the lightning deal you want to request. If not specified, the entire list will be provided.

------

## Optional Parameters

- `state`: Limit the returned lightning deals by their state.

  **Possible values:**

  - `AVAILABLE`
  - `WAITLIST`
  - `SOLDOUT`
  - `WAITLISTFULL`
  - `EXPIRED`
  - `SUPPRESSED`

  **Example:**

  - `&state=AVAILABLE`

------

## Response

An array of [lightning deal objects](https://discuss.keepa.com/t/lightning-deal-object/9760) in the `lightningDeals` field.



# Tracking Products

**Token Cost:** Varies per tracked product

Keepa can track product changes and notify you. Tracking through our API uses a separate list than your Keepa account. You can only view and manage the products you track through API calls.

**Important Notes:**

- Each tracked product **decreases your token refill** rate. Once your refill rate reaches **0**, you will not be able to track any more products or make any API requests that require tokens.
- If your API access is terminated, your tracking list will be deactivated and removed after **7 days**, unless access is restored.
- If you switch to a lower-tier API plan that doesn’t provide enough tokens for your current tracking list, the necessary amount of trackings will be deactivated and slated for removal after 7 days, unless they are reactivated in the interim.
- To manage your tracking expenses separately from other API uses, consider operating two separate Keepa accounts, each with its own API subscription.

------

## Types of Tracking

There are two types of tracking:

1. **Regular Tracking**
   - Allows tracking of the following price types:
     - Amazon
     - New
     - Used
     - List
     - Collectible
     - Refurbished
     - Lightning Deal
     - All offer counts
     - Sales Rank
2. **Marketplace Tracking**
   - Includes all features of Regular Tracking.
   - Additionally tracks:
     - Warehouse Deals
     - Buy Box New & Used
     - New 3rd Party FBA & FBM
     - Rating
     - Prime Exclusive
     - Review Counts
     - All Used and Collectible conditions with shipping costs.
   - The first 20 offers of a product will be used for the tracking.

------

Each tracked ASIN can have notification rules for multiple Amazon locales and have a different update interval. These factors determine how much your token refill rate is reduced for each tracking:

- **Regular Tracking:** **0.9 tokens** per update per locale tracked
- **Marketplace Tracking:** **9 tokens** per update per locale tracked

Since the token refill rate is an integer, the tracking reduction rate is rounded. Your current reduction rate is part of every API response in the `tokenFlowReduction` field alongside other token stats. Your `tokenFlowReduction` will be updated every 5 minutes—not immediately after adding or removing trackings.

**Token Cost Examples:**

- 2000 Regular Trackings



  on a single locale with an update interval of 1 hour:

  - 2000 × 0.9 tokens/hour = 1800 tokens/hour = 30 tokens/minute
  - **Decreased refill rate:** 30 tokens

- 700 Marketplace Trackings



  on a single locale with an update interval of 12 hours:

  - 700 × 9 tokens/12 hours = 525 tokens/hour = 8.75 tokens/minute
  - **Decreased refill rate:** 9 tokens

You can track as many products as your token rate allows.

------

## Named Tracking Lists

It is possible to use named tracking lists, which act as a logical separation of your tracking objects. This enables you to have multiple, different trackings for the same ASIN. By default, all trackings are managed in an unnamed list.

- All tracking requests (except **Set Webhook**) support the additional parameter `list` to specify the name of the list the request should act on (e.g., `&list=user123`).
- A list name can be up to **64** characters long.
- You can manage up to **100,000** lists (contact us if you need more).
- Lists are created implicitly with the first added tracking and can be deleted by the **Remove All** request.
- If a tracking is added to a named list, the tracking object will have the list name set in the `trackingListName`. The same applies to notification objects.
- You can retrieve a list of all your named lists using the **Get Named Lists** request.

------

## Managing Your Tracking

To manage your API tracking, use the following commands:

- **Add Tracking**: Add a new tracking to your list.
- **Remove Tracking**: Remove a tracking from your list or clear your entire list.
- **Get Tracking**: Retrieve tracking information for a product on your list or the whole list.
- **Get Notifications**: Retrieve recent notifications.
- **Get Named Lists**: Retrieve a list of all your named tracking lists.
- **Set Webhook**: Update your webhook URL to receive push notifications.

------

### Add Tracking

**Token Cost:** 1 per tracking

Adds a new tracking to your list. If you already have an existing tracking for the ASIN on your list, it will be overridden, and if it was deactivated, it will be reactivated. You can batch up to **1,000** trackings in a single request to significantly speed up the process of adding multiple trackings.

**Query:**

You can choose between an HTTP GET or POST request.

#### GET Format

```bash
/tracking?key=<yourAccessKey>&type=add&tracking=<trackingJSON>
```

- `<yourAccessKey>`: Your private API key.
- `<trackingJSON>`: The tracking JSON contains an array of [tracking creation objects](https://discuss.keepa.com/t/tracking-creation-object/2068). It must be URL-encoded if the GET format is used. Due to URL length limitations, do not use the GET method for batch requests.

#### POST Format

```bash
/tracking?key=<yourAccessKey>&type=add
```

- `<yourAccessKey>`: Your private API key.
- **POST payload**: Must contain a single or an array of [tracking creation objects](https://discuss.keepa.com/t/tracking-creation-object/2068). You can specify up to **1,000** tracking creation objects in a single request in JSON array notation: `[object, object, ...]`.

**Response:**

- A `trackings` array field containing the created or updated [tracking object(s)](https://discuss.keepa.com/t/tracking-object/2067).
- If an error occurred, the `error` field is set.
- If a tracking could not be added in a batch request, the `error` field will include a comma-separated list of all failed ASINs.

------

### Remove Tracking

**Token Cost:** 0

Removes a single tracking from your list.

**Query:**

```lua
/tracking?key=<yourAccessKey>&type=remove&asin=<ASIN>
```

- `<yourAccessKey>`: Your private API key.
- `<ASIN>`: The ASIN of the product you want to remove from your tracking list.

To remove all your trackings with a single call:

```bash
/tracking?key=<yourAccessKey>&type=removeAll
```

**Response:**

- Only token bucket information.
- If you did not have a tracking for the specified ASIN, the `error` field is set.
- Note that your `tokenFlowReduction` will not be updated immediately upon removing a tracking.

------

### Get Tracking

**Token Cost:** 0

Retrieves a single tracking from your list.

**Query:**

```bash
/tracking?key=<yourAccessKey>&type=get&asin=<ASIN>
```

- `<yourAccessKey>`: Your private API key.
- `<ASIN>`: The ASIN of the product you want to retrieve your tracking for.

#### Retrieve your list

```php-template
/tracking?key=<yourAccessKey>&type=list[&asins-only=1][&page=<n>&perPage=<m>]
```

- `asins-only=1` | Returns only the ASINs you track (fast, lightweight). Pagination parameters are **ignored** in this mode because the call always returns the full list.

- `page` Page of the batch you want (first page = `0`).

- `perPage` Number of tracking records to return in one batch, maximum 100,000.

  ##### Pagination details

  Default values: `page=0`, `perPage=100,000`. If your total list is bigger, fetch it in batches until the response array is empty.

**Response:**

- A `trackings` field containing the [tracking object(s)](https://discuss.keepa.com/t/tracking-object/2067) (always an array).
- If you did not have a tracking for the specified ASIN, the `error` field is set.
- In case of the `list` operation with the `asins-only` parameter, an `asinList` field containing a string array of all tracked ASINs.

------

### Get Notifications

**Token Cost:** 0

Retrieves your recent [notification objects](https://discuss.keepa.com/t/notification-object/2069). A notification will be marked as read once delivered through this call or pushed to your webhook. Notifications are deleted **24 hours** after creation. Use this request if you do not want to use push notifications via webhook or if your webhook endpoint was offline.

**Query:**

```php-template
/tracking?key=<yourAccessKey>&type=notification&since=<since>&revise=<revise>
```

- `<yourAccessKey>`: Your private API key.
- `<since>`: Retrieve all available notifications that occurred since this date, in KeepaTime minutes.
- `<revise>`: Boolean value (`0` = false, `1` = true). Whether or not to request notifications already marked as read.

**Response:**

- A `notifications` field containing [notification object(s)](https://discuss.keepa.com/t/notification-object/2069), sorted by most recent first. Always an array.

------

### Get Named Lists

**Token Cost:** 0

Retrieves a list of all the names of your named lists.

**Query:**

```bash
/tracking?key=<yourAccessKey>&type=listNames
```

- `<yourAccessKey>`: Your private API key.

**Response:**

- A `trackingListNames` field containing the names of all your named lists. Always an array.

------

### Set Webhook

**Token Cost:** 0

Updates the webhook URL our service will call whenever a notification is triggered. The URL can also be updated and tested via the [website](https://keepa.com/#!api).

**Push Notification Details:**

- A push notification will be an HTTP POST call with a single [notification object](https://discuss.keepa.com/t/notification-object/2069) as its content.
- Your server must respond with a status code of **200** to confirm successful retrieval.
- If delivery fails, a second attempt will be made with a **15-second** delay.
- **Note:** The content type of the POST is `application/json` and **not** `application/x-www-form-urlencoded`. If you use PHP, you have to use `file_get_contents('php://input')` or `$HTTP_RAW_POST_DATA` to access the content.

**Query:**

```bash
/tracking?key=<yourAccessKey>&type=webhook&url=<URL>
```

- `<yourAccessKey>`: Your private API key.
- `<URL>`: The new webhook URL.

**Response:**

- Only token bucket information if the update was successful.
- If the specified URL is of invalid format, the `error` field is set.



# Product Request

**Token Cost:** 1 per product

Retrieves the [product object](https://discuss.keepa.com/t/product-object/116) for the specified ASIN and domain. If our last update is older than ~1 hour, it will be automatically refreshed before being delivered to ensure near real-time pricing data.

You can request products via either their ASIN (preferred) or UPC and EAN codes. You cannot use both parameters, `asin` and `code`, in the same request. If you use the `code` parameter and the provided code is not in our database, no product will be returned. In this case, you can use the product search instead to look up the code on Amazon. Keepa cannot track Amazon Fresh.

------

## Query

```php-template
/product?key=<yourAccessKey>&domain=<domainId>&asin=<ASIN> [or] &code=<productCode>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access. Valid values:

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |
  | **12**    | com.br |

- `<ASIN>`: The ASIN of the product you want to request. For batch requests, a comma-separated list of ASINs (up to 100).

- `<productCode>`: The product code of the product you want to request. We currently allow UPC, EAN, and ISBN-13 codes. For batch requests, a comma-separated list of codes (up to 100). Multiple ASINs can have the same product code, so requesting a product code can return multiple products. Use the `code-limit` parameter to limit the number of returned products per code.

------

## Optional Parameters

- `stats`: Include a `stats` field with current prices and statistics.
- `update`: Force a refresh if the product’s last update is older than specified hours.
- `history`: Exclude historical data fields to reduce response size and processing time.
- `days`: Limit historical data to the recent X days.
- `code-limit`: Limit the number of products returned per code when using the `code` parameter.
- `offers`: Retrieve up-to-date marketplace offers; incurs additional token cost.
- `only-live-offers`: Include only live marketplace offers; reduces response size.
- `rental`: Collect rental prices when available.
- `videos`: Include video metadata.
- `aplus`: Include A+ content.
- `rating`: Include existing rating and review count history; may consume an extra token.
- `buybox`: Include Buy Box related data; incurs additional token cost.
- `stock`: Include stock information in offers; incurs additional token cost.
- `historical-variations`: Include historical and out of stock variations; incurs additional token cost.

------

### `stats`

**Token Cost:** No extra token cost

If specified, the product object will include a `stats` field with quick access to current prices, min/max prices, and weighted mean values. If the `offers` parameter is used, it will also provide Buy Box information.

You can provide the `stats` parameter in two forms:

- **Last x days** (positive integer value): Calculates the stats for the last **x** days.
- **Interval**: Specify a date range for the stats calculation using two timestamps (Unix epoch time in milliseconds) or two date strings (ISO8601 format, UTC).

**Note:** If there is insufficient historical data for a price type, the actual interval of the weighted mean calculation may be shorter than specified. All data provided via the `stats` field are calculated using the product object’s `csv` history field; no new data is provided through this parameter.

**Examples:**

- `&stats=180` (last 180 days)
- `&stats=2015-10-20,2015-12-24` (from Oct 20 to Dec 24, 2015)
- `&stats=2011-01-01,2025-01-01` (entire history)
- `&stats=1445299200000,1450915200000` (Unix epoch time in milliseconds, from Oct 20 to Dec 24, 2015)

------

### `update`

**Additional Token Cost:** 0 or 1 per product

Positive integer value. If the product’s last update is older than **update** hours, force a refresh. The default value used by the API is 1 hour. This parameter also works in conjunction with the `offers` parameter.

Using this parameter, you can achieve the following:

- **Speed up requests:** If up-to-date data is not required, use a higher value than **1** hour. No extra token cost.
- **Always retrieve live data:** Use the value **0**. If our last update was less than 1 hour ago, this consumes **1 extra token**.
- **No update at all:** Use the value **-1**. If the product is missing in our database and the `asin` parameter was used, the product request will consume **0 tokens**, and you will not receive any product data. Use this if you are only interested in products we have historical data for to save tokens.
- **Reduced offers token usage:** When combined with the `offers` parameter and our last offers data update is newer than **update** hours, the offers token usage will be reduced to 5 tokens, and no update will take place, regardless of the number of offer pages requested.

**Example:**

- `&update=48` (only trigger an update if the product’s last update is older than 48 hours)

------

### `history`

**Token Cost:** No extra token cost

Boolean value (`0` = false, `1` = true). If specified and set to `0`, the product object will not include the `csv`, `salesRanks`, `monthlySoldHistory`, `parentAsinHistory`, `couponHistory`, `buyBoxSellerIdHistory`, `buyBoxUsedHistory` and `salesRankReferenceHistory` fields. If you do not need them, use this to have them removed from the response. This will improve processing time and considerably decrease the size of the response.

**Example:**

- `&history=0`

------

### `days`

**Token Cost:** No extra token cost

Any positive integer value. If specified with a positive value **X**, the product object will limit all historical data to the recent **X** days. This includes the `csv`, `buyBoxSellerIdHistory`, `salesRankReferenceHistory`, `salesRanks`, `offers`, and `offers.offerCSV` fields. If you do not need old historical data, use this to reduce the response size and improve processing time. The parameter does not use calendar days; so **1 day** equals the last 24 hours.

**Example:**

- `&days=90`

------

### `code-limit`

**Token Cost:** No extra token cost

Any positive integer value. Sets a constraint on the maximum number of products returned for a given code when utilizing the `code` parameter. Use this parameter to limit the volume of product results associated with specific product codes.

**Example:**

- `&code-limit=10`

------

### `offers`

**Token Cost:** 6 for every found offer page (contains up to 10 offers) per product

Positive integer value between **20** and **100**. Determines the number of **up-to-date** marketplace offers to retrieve. The additional token cost is calculated based on the number of found offers, not the requested amount (as a product can have fewer offers than requested). When using the `offers` parameter, the basic 1 token cost per ASIN of the product request does not apply.

If the `offers` parameter is used, the product object will contain additional data:

- [Marketplace offer objects](https://discuss.keepa.com/t/marketplace-offer-object/807)
- Information on the New and Used Buy Box, including a history of Buy Box winners
- Price history data for FBA (Fulfillment by Amazon), FBM (Fulfillment by Merchant), Warehouse Deals, Prime exclusive, and all Used and Collectible sub-conditions, including shipping and handling costs
- Rating and review count history

All offers-related data is updated independently, irregularly, and not as often as all other product data. Keep this in mind when evaluating the additional historical data.

**Notes:**

- The returned product may have more offers than specified because we keep a history of offers. The number specified in this parameter determines how many offers we attempt to retrieve/update from Amazon. Each offer object has a `lastSeen` field that can be used to filter up-to-date offers.
- Batched requests are processed in parallel.
- All offers-related data is freshly updated and up-to-date.
- The request will require more time to complete, ranging from 2 to 20 seconds with an average of 5 seconds. Use batch requests or parallel requests to increase throughput when required.
- If we fail to retrieve/refresh the offers data, the request will consume 1 token. The request will return successfully and will contain, if available, all **historical** offers (unless `only-live-offers` is used) and product data. You can retry the request after a few minutes.

**Limitations:**

- Not available for digital products, movie rentals, product bundles, Amazon Fresh, and Amazon Pantry.

**Example:**

- `&offers=40` (Requested up to 40 offers, but the product only has 18 offers.)
  - **Total token cost for the request:** 6 per found offer page = 12 tokens.

------

### `only-live-offers`

**Token Cost:** No extra token cost

Boolean value (`0` = false, `1` = true). If specified and set to `1`, the product object will only include live marketplace offers (when used in combination with the `offers` parameter). If you do not need historical offers, use this to reduce the response size and improve processing time.

**Example:**

- `&only-live-offers=1`

------

### `rental`

**Token Cost:** No extra token cost

Boolean value (`0` = false, `1` = true). Can only be used in conjunction with the `offers` parameter. If specified and set to `1`, the rental price will be collected when available.

**Note:** Rental prices are only available for Amazon US and only for books (not for eBooks).

------

### `videos`

**Token Cost:** No extra token cost

Boolean value (`0` = false, `1` = true). If specified and set to `1`, the videos metadata will be provided when available. Using this parameter does not trigger an update to the videos data; it only gives access to our existing data if available. If you need up-to-date data, you have to use the `offers` parameter.

------

### `aplus`

**Token Cost:** No extra token cost

Boolean value (`0` = false, `1` = true). If specified and set to `1`, the A+ content will be provided when available. Using this parameter does not trigger an update to the A+ content; it only gives access to our existing data if available. If you need up-to-date data, you have to use the `offers` parameter.

------

### `rating`

**Token Cost:** Up to 1 extra token per product

Boolean value (`0` = false, `1` = true). If specified and set to `1`, the product object will include our existing `RATING` and `COUNT_REVIEWS` history in the `csv` field, regardless of whether the `offers` parameter is used. The extra token will only be consumed if our last update to both data points is less than 14 days ago.

Using this parameter does not trigger an update to those two fields; it only gives access to our existing data if available. If you need up-to-date data, you have to use the `offers` parameter. Use this if you need access to the rating data, which may be outdated, but do not need any other data fields provided through the `offers` parameter to save tokens and speed up the request. If there is no rating data returned, you can still make another request using the `offers` parameter.

**Example:**

- `&rating=1` (Include the rating and review count data in the `csv` history data field of the product object and respective fields of the statistics object)

------

### `buybox`

**Additional Token Cost:** 2 per product

Boolean value (`0` = false, `1` = true). If specified and set to `1`, the product and statistics object will include all available Buy Box related data:

- Current price, price history, and statistical values
- `buyBoxSellerIdHistory`
- All Buy Box fields in the statistics object

The `buybox` parameter does not trigger a fresh data collection. If the `offers` parameter is used, the `buybox` parameter is ignored, as the `offers` parameter also provides access to all Buy Box related data. To access the statistics object, the `stats` parameter is required.

**Example:**

- `&buybox=1`

------

### `stock`

**Additional Token Cost:** 2 per product

Boolean value (`0` = false, `1` = true). If specified together with the `offers` parameter and set to `1`, the marketplace offer objects will include the `stockCSV` field, and the product object will include the `lastStockUpdate` field.

**Token Cost Note:** The `stock` parameter incurs 2 extra tokens only if `lastStockUpdate` is newer than 7 days.

**Note:** The `stock` parameter is not guaranteed to avoid triggering a fresh stock data collection. The request will require more time to retrieve stock data, ranging from 1 to 2 seconds per offer.

**Example:**

- `&stock=1`
-

------

### `historical-variations`

**Additional Token Cost:** 1 per product that has a parent ASIN

Boolean value (`0` = false, `1` = true). If specified and set to `1`, the product object will have the `historicalVariations` field set, which provides a list of historical and out of stock variation ASINs of the requested product.

**Example:**

- `&historical-variations=1`

------

## Response

A `products` field containing an array of [product objects](https://discuss.keepa.com/t/product-object/116) with an entry for each ASIN that was requested.



## Product Finder

**Token Costs:** 10 + 1 per 100 ASINs

Search for products in our database that match your specified criteria and receive a Search Insights summary that aggregates KPIs (prices, seller mix, brand counts, etc.) across the entire result set. You can search and sort by nearly all product fields. This request offers the same core functionality as our [Product Finder](https://keepa.com/#!finder).

- The request returns only ASIN lists, not product objects.
- Each request consumes 10 tokens plus an additional token per 100 ASINs in the result set.
- A query can return up to 10,000 ASINs using paging, with a minimum page size of 50 ASINs. If using paging, initial search results are not cached, so the order of results may be inconsistent between individual pages if there is a delay between consecutive page requests.
  **Note:** All API requests execute regardless of your current token balance, as long as it’s positive. Requesting large result sets may cause your token balance to go negative. Use with caution!
- Filters are joined by an **AND** condition.
- For filters allowing multiple entries (all arrays), each specified entry is considered with an **OR** condition, supporting a maximum of 50 entries.
- The product query searches our database, not Amazon’s. It may not find all products on Amazon that match your query.
- Product data constantly changes. Running the same query twice may yield different results, as products may be misplaced due to recent changes or updates during the query execution.

------

**Query:**

You can choose between an HTTP GET or POST request.

**GET format:**

```php-template
/query?key=<yourAccessKey>&domain=<domainId>&selection=<queryJSON>[&stats=1]
```

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access. Valid values:

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |
  | **12**    | com.br |

- `<queryJSON>`: The query JSON containing all request parameters. It must be URL-encoded if the GET format is used.

**POST format:**

```php-template
/query?domain=<domainId>&key=<yourAccessKey>[&stats=1]
```

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access. Valid values:

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |
  | **12**    | com.br |

- The POST payload must contain a `<queryJSON>`.

------

**queryJSON Format:**

```
{
	"page": Integer,
	"perPage": Integer,
	"rootCategory": Long array,
	"categories_include": Long array,
	"categories_exclude": Long array,
	"salesRankReference": Long,
	"manufacturer": String array,
	"title": String,
	"singleVariation": Boolean,
	"lastPriceChange_lte": Integer,
	"lastPriceChange_gte": Integer,
	"lastOffersUpdate_lte": Integer,
	"lastOffersUpdate_gte": Integer,
	"isLowestOffer": Boolean,
	"productType": Integer,
	"hasParentASIN": Boolean,
	"availabilityAmazon": Integer array,
	"returnRate": Integer array,
	"hasReviews": Boolean,
	"trackingSince_lte": Integer,
	"trackingSince_gte": Integer,
	"brand": String array,
	"productGroup": String array,
	"partNumber": String array,
	"model": String array,
	"color": String array,
	"size": String array,
	"edition": String array,
	"format": String array,
	"packageHeight_lte": Integer,
	"packageHeight_gte": Integer,
	"packageLength_lte": Integer,
	"packageLength_gte": Integer,
	"packageWidth_lte": Integer,
	"packageWidth_gte": Integer,
	"packageWeight_lte": Integer,
	"packageWeight_gte": Integer,,
	"itemHeight_lte": Integer,
	"itemHeight_gte": Integer,
	"itemLength_lte": Integer,
	"itemLength_gte": Integer,
	"itemWidth_lte": Integer,
	"itemWidth_gte": Integer,
	"itemWeight_lte": Integer,
	"itemWeight_gte": Integer,
	"variationCount_lte": Integer,
	"variationCount_gte": Integer,
	"imageCount_lte": Integer,
	"imageCount_gte": Integer,
	"buyBoxStatsAmazon30_lte": Integer,
	"buyBoxStatsAmazon30_gte": Integer,
	"buyBoxStatsAmazon90_lte": Integer,
	"buyBoxStatsAmazon90_gte": Integer,
	"buyBoxStatsAmazon180_lte": Integer,
	"buyBoxStatsAmazon180_gte": Integer,
	"buyBoxStatsAmazon365_lte": Integer,
	"buyBoxStatsAmazon365_gte": Integer,
	"buyBoxStatsTopSeller30_lte": Integer,
	"buyBoxStatsTopSeller30_gte": Integer,
	"buyBoxStatsTopSeller90_lte": Integer,
	"buyBoxStatsTopSeller90_gte": Integer,
	"buyBoxStatsTopSeller180_lte": Integer,
	"buyBoxStatsTopSeller180_gte": Integer,
	"buyBoxStatsTopSeller365_lte": Integer,
	"buyBoxStatsTopSeller365_gte": Integer,
	"buyBoxStatsSellerCount30_lte": Integer,
	"buyBoxStatsSellerCount30_gte": Integer,
	"buyBoxStatsSellerCount90_lte": Integer,
	"buyBoxStatsSellerCount90_gte": Integer,
	"buyBoxStatsSellerCount180_lte": Integer,
	"buyBoxStatsSellerCount180_gte": Integer,
	"buyBoxStatsSellerCount365_lte": Integer,
	"buyBoxStatsSellerCount365_gte": Integer,
	"outOfStockPercentage90_lte": Integer,
	"outOfStockPercentage90_gte": Integer,
	"variationReviewCount_lte": Integer,
	"variationReviewCount_gte": Integer,
	"variationRatingCount_lte": Integer,
	"variationRatingCount_gte": Integer,
	"deltaPercent90_monthlySold_lte": Integer,
	"deltaPercent90_monthlySold_gte": Integer,
	"outOfStockCountAmazon30_lte": Integer,
	"outOfStockCountAmazon30_gte": Integer,
	"outOfStockCountAmazon90_lte": Integer,
	"outOfStockCountAmazon90_gte": Integer,
	"isHazMat": Boolean,
	"isHeatSensitive": Boolean,
	"isAdultProduct": Boolean,
	"isEligibleForTradeIn": Boolean,
	"isEligibleForSuperSaverShipping": Boolean,
	"isSNS": Boolean,
	"buyBoxIsPreorder": Boolean,
	"buyBoxIsBackorder": Boolean,
	"buyBoxIsPrimeExclusive": Boolean,
	"author": String array,
	"binding": String array,
	"genre": String array,
	"languages": String array,
	"publisher": String array,
	"platform": String array,
	"activeIngredients": String array,
	"specialIngredients": String array,
	"itemTypeKeyword": String array,
	"targetAudienceKeyword": String array,
	"itemForm": String array,
	"scent": String array,
	"unitType": String array,
	"pattern": String array,
	"style": String array,
	"material": String array,
	"frequentlyBoughtTogether": String array,
	"couponOneTimeAbsolute_lte": Integer,
	"couponOneTimeAbsolute_gte": Integer,
	"couponOneTimePercent_lte": Integer,
	"couponOneTimePercent_gte": Integer,
	"couponSNSPercent_lte": Integer,
	"couponSNSPercent_gte": Integer,
	"flipability30_lte": Byte,
	"flipability30_gte": Byte,
	"flipability90_lte": Byte,
	"flipability90_gte": Byte,
	"flipability365_lte": Byte,
	"flipability365_gte": Byte,
	"businessDiscount_lte": Byte,
	"businessDiscount_gte": Byte,
	"batteriesRequired": Boolean,
	"batteriesIncluded": Boolean,
	"isMerchOnDemand": Boolean,
	"hasMainVideo": Boolean,
	"hasAPlus": Boolean,
	"hasAPlusFromManufacturer": Boolean,
	"videoCount_lte": Byte,
	"videoCount_gte": Byte,
	"brandStoreName": String array,
	"brandStoreUrlName": String array,
	"buyBoxIsAmazon": Boolean,
	"buyBoxIsFBA": Boolean,
	"buyBoxIsUnqualified": Boolean,
	"buyBoxSellerId": String array,
	"buyBoxUsedCondition": Integer array,
	"buyBoxUsedIsFBA": Boolean,
	"buyBoxUsedSellerId": String array,
	"sellerIds": String array,
	"sellerIdsLowestFBA": String array,
	"sellerIdsLowestFBM": String array,
	"numberOfItems_lte": Integer,
	"numberOfItems_gte": Integer,
	"numberOfPages_lte": Integer,
	"numberOfPages_gte": Integer,
	"publicationDate_lte": Integer,
	"publicationDate_gte": Integer,
	"releaseDate_lte": Integer,
	"releaseDate_gte": Integer,
	"isPrimeExclusive": Boolean,
	"lightningEnd_lte": Integer,
	"lightningEnd_gte": Integer,
	"monthlySold_lte": Integer,
	"monthlySold_gte": Integer
	"current_AMAZON_lte": Integer,
	"current_AMAZON_gte": Integer,
	"current_NEW_lte": Integer,
	"current_NEW_gte": Integer,
	"current_USED_lte": Integer,
	"current_USED_gte": Integer,
	"current_SALES_lte": Integer,
	"current_SALES_gte": Integer,
	"current_LISTPRICE_lte": Integer,
	"current_LISTPRICE_gte": Integer,
	"current_COLLECTIBLE_lte": Integer,
	"current_COLLECTIBLE_gte": Integer,
	"current_REFURBISHED_lte": Integer,
	"current_REFURBISHED_gte": Integer,
	"current_NEW_FBM_SHIPPING_lte": Integer,
	"current_NEW_FBM_SHIPPING_gte": Integer,
	"current_LIGHTNING_DEAL_lte": Integer,
	"current_LIGHTNING_DEAL_gte": Integer,
	"current_WAREHOUSE_lte": Integer,
	"current_WAREHOUSE_gte": Integer,
	"current_NEW_FBA_lte": Integer,
	"current_NEW_FBA_gte": Integer,
	"current_COUNT_NEW_lte": Integer,
	"current_COUNT_NEW_gte": Integer,
	"current_COUNT_USED_lte": Integer,
	"current_COUNT_USED_gte": Integer,
	"current_COUNT_REFURBISHED_lte": Integer,
	"current_COUNT_REFURBISHED_gte": Integer,
	"current_COUNT_COLLECTIBLE_lte": Integer,
	"current_COUNT_COLLECTIBLE_gte": Integer,
	"current_RATING_lte": Integer,
	"current_RATING_gte": Integer,
	"current_COUNT_REVIEWS_lte": Integer,
	"current_COUNT_REVIEWS_gte": Integer,
	"current_BUY_BOX_SHIPPING_lte": Integer,
	"current_BUY_BOX_SHIPPING_gte": Integer,
	"current_USED_NEW_SHIPPING_lte": Integer,
	"current_USED_NEW_SHIPPING_gte": Integer,
	"current_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"current_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"current_USED_GOOD_SHIPPING_lte": Integer,
	"current_USED_GOOD_SHIPPING_gte": Integer,
	"current_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"current_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"current_REFURBISHED_SHIPPING_lte": Integer,
	"current_REFURBISHED_SHIPPING_gte": Integer,
	"current_TRADE_IN_lte": Integer,
	"current_TRADE_IN_gte": Integer,
	"delta90_AMAZON_lte": Integer,
	"delta90_AMAZON_gte": Integer,
	"delta90_NEW_lte": Integer,
	"delta90_NEW_gte": Integer,
	"delta90_USED_lte": Integer,
	"delta90_USED_gte": Integer,
	"delta90_SALES_lte": Integer,
	"delta90_SALES_gte": Integer,
	"delta90_LISTPRICE_lte": Integer,
	"delta90_LISTPRICE_gte": Integer,
	"delta90_COLLECTIBLE_lte": Integer,
	"delta90_COLLECTIBLE_gte": Integer,
	"delta90_REFURBISHED_lte": Integer,
	"delta90_REFURBISHED_gte": Integer,
	"delta90_NEW_FBM_SHIPPING_lte": Integer,
	"delta90_NEW_FBM_SHIPPING_gte": Integer,
	"delta90_LIGHTNING_DEAL_lte": Integer,
	"delta90_LIGHTNING_DEAL_gte": Integer,
	"delta90_WAREHOUSE_lte": Integer,
	"delta90_WAREHOUSE_gte": Integer,
	"delta90_NEW_FBA_lte": Integer,
	"delta90_NEW_FBA_gte": Integer,
	"delta90_COUNT_NEW_lte": Integer,
	"delta90_COUNT_NEW_gte": Integer,
	"delta90_COUNT_USED_lte": Integer,
	"delta90_COUNT_USED_gte": Integer,
	"delta90_COUNT_REFURBISHED_lte": Integer,
	"delta90_COUNT_REFURBISHED_gte": Integer,
	"delta90_COUNT_COLLECTIBLE_lte": Integer,
	"delta90_COUNT_COLLECTIBLE_gte": Integer,
	"delta90_RATING_lte": Integer,
	"delta90_RATING_gte": Integer,
	"delta90_COUNT_REVIEWS_lte": Integer,
	"delta90_COUNT_REVIEWS_gte": Integer,
	"delta90_BUY_BOX_SHIPPING_lte": Integer,
	"delta90_BUY_BOX_SHIPPING_gte": Integer,
	"delta90_USED_NEW_SHIPPING_lte": Integer,
	"delta90_USED_NEW_SHIPPING_gte": Integer,
	"delta90_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"delta90_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"delta90_USED_GOOD_SHIPPING_lte": Integer,
	"delta90_USED_GOOD_SHIPPING_gte": Integer,
	"delta90_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"delta90_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"delta90_REFURBISHED_SHIPPING_lte": Integer,
	"delta90_REFURBISHED_SHIPPING_gte": Integer,
	"delta90_TRADE_IN_lte": Integer,
	"delta90_TRADE_IN_gte": Integer,
	"delta30_AMAZON_lte": Integer,
	"delta30_AMAZON_gte": Integer,
	"delta30_NEW_lte": Integer,
	"delta30_NEW_gte": Integer,
	"delta30_USED_lte": Integer,
	"delta30_USED_gte": Integer,
	"delta30_SALES_lte": Integer,
	"delta30_SALES_gte": Integer,
	"delta30_LISTPRICE_lte": Integer,
	"delta30_LISTPRICE_gte": Integer,
	"delta30_COLLECTIBLE_lte": Integer,
	"delta30_COLLECTIBLE_gte": Integer,
	"delta30_REFURBISHED_lte": Integer,
	"delta30_REFURBISHED_gte": Integer,
	"delta30_NEW_FBM_SHIPPING_lte": Integer,
	"delta30_NEW_FBM_SHIPPING_gte": Integer,
	"delta30_LIGHTNING_DEAL_lte": Integer,
	"delta30_LIGHTNING_DEAL_gte": Integer,
	"delta30_WAREHOUSE_lte": Integer,
	"delta30_WAREHOUSE_gte": Integer,
	"delta30_NEW_FBA_lte": Integer,
	"delta30_NEW_FBA_gte": Integer,
	"delta30_COUNT_NEW_lte": Integer,
	"delta30_COUNT_NEW_gte": Integer,
	"delta30_COUNT_USED_lte": Integer,
	"delta30_COUNT_USED_gte": Integer,
	"delta30_COUNT_REFURBISHED_lte": Integer,
	"delta30_COUNT_REFURBISHED_gte": Integer,
	"delta30_COUNT_COLLECTIBLE_lte": Integer,
	"delta30_COUNT_COLLECTIBLE_gte": Integer,
	"delta30_RATING_lte": Integer,
	"delta30_RATING_gte": Integer,
	"delta30_COUNT_REVIEWS_lte": Integer,
	"delta30_COUNT_REVIEWS_gte": Integer,
	"delta30_BUY_BOX_SHIPPING_lte": Integer,
	"delta30_BUY_BOX_SHIPPING_gte": Integer,
	"delta30_USED_NEW_SHIPPING_lte": Integer,
	"delta30_USED_NEW_SHIPPING_gte": Integer,
	"delta30_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"delta30_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"delta30_USED_GOOD_SHIPPING_lte": Integer,
	"delta30_USED_GOOD_SHIPPING_gte": Integer,
	"delta30_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"delta30_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"delta30_REFURBISHED_SHIPPING_lte": Integer,
	"delta30_REFURBISHED_SHIPPING_gte": Integer,
	"delta30_TRADE_IN_lte": Integer,
	"delta30_TRADE_IN_gte": Integer,
	"deltaPercent90_AMAZON_lte": Integer,
	"deltaPercent90_AMAZON_gte": Integer,
	"deltaPercent90_NEW_lte": Integer,
	"deltaPercent90_NEW_gte": Integer,
	"deltaPercent90_USED_lte": Integer,
	"deltaPercent90_USED_gte": Integer,
	"deltaPercent90_SALES_lte": Integer,
	"deltaPercent90_SALES_gte": Integer,
	"deltaPercent90_LISTPRICE_lte": Integer,
	"deltaPercent90_LISTPRICE_gte": Integer,
	"deltaPercent90_COLLECTIBLE_lte": Integer,
	"deltaPercent90_COLLECTIBLE_gte": Integer,
	"deltaPercent90_REFURBISHED_lte": Integer,
	"deltaPercent90_REFURBISHED_gte": Integer,
	"deltaPercent90_NEW_FBM_SHIPPING_lte": Integer,
	"deltaPercent90_NEW_FBM_SHIPPING_gte": Integer,
	"deltaPercent90_LIGHTNING_DEAL_lte": Integer,
	"deltaPercent90_LIGHTNING_DEAL_gte": Integer,
	"deltaPercent90_WAREHOUSE_lte": Integer,
	"deltaPercent90_WAREHOUSE_gte": Integer,
	"deltaPercent90_NEW_FBA_lte": Integer,
	"deltaPercent90_NEW_FBA_gte": Integer,
	"deltaPercent90_COUNT_NEW_lte": Integer,
	"deltaPercent90_COUNT_NEW_gte": Integer,
	"deltaPercent90_COUNT_USED_lte": Integer,
	"deltaPercent90_COUNT_USED_gte": Integer,
	"deltaPercent90_COUNT_REFURBISHED_lte": Integer,
	"deltaPercent90_COUNT_REFURBISHED_gte": Integer,
	"deltaPercent90_COUNT_COLLECTIBLE_lte": Integer,
	"deltaPercent90_COUNT_COLLECTIBLE_gte": Integer,
	"deltaPercent90_RATING_lte": Integer,
	"deltaPercent90_RATING_gte": Integer,
	"deltaPercent90_COUNT_REVIEWS_lte": Integer,
	"deltaPercent90_COUNT_REVIEWS_gte": Integer,
	"deltaPercent90_BUY_BOX_SHIPPING_lte": Integer,
	"deltaPercent90_BUY_BOX_SHIPPING_gte": Integer,
	"deltaPercent90_USED_NEW_SHIPPING_lte": Integer,
	"deltaPercent90_USED_NEW_SHIPPING_gte": Integer,
	"deltaPercent90_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"deltaPercent90_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"deltaPercent90_USED_GOOD_SHIPPING_lte": Integer,
	"deltaPercent90_USED_GOOD_SHIPPING_gte": Integer,
	"deltaPercent90_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"deltaPercent90_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"deltaPercent90_REFURBISHED_SHIPPING_lte": Integer,
	"deltaPercent90_REFURBISHED_SHIPPING_gte": Integer,
	"deltaPercent90_TRADE_IN_lte": Integer,
	"deltaPercent90_TRADE_IN_gte": Integer,
	"deltaPercent30_AMAZON_lte": Integer,
	"deltaPercent30_AMAZON_gte": Integer,
	"deltaPercent30_NEW_lte": Integer,
	"deltaPercent30_NEW_gte": Integer,
	"deltaPercent30_USED_lte": Integer,
	"deltaPercent30_USED_gte": Integer,
	"deltaPercent30_SALES_lte": Integer,
	"deltaPercent30_SALES_gte": Integer,
	"deltaPercent30_LISTPRICE_lte": Integer,
	"deltaPercent30_LISTPRICE_gte": Integer,
	"deltaPercent30_COLLECTIBLE_lte": Integer,
	"deltaPercent30_COLLECTIBLE_gte": Integer,
	"deltaPercent30_REFURBISHED_lte": Integer,
	"deltaPercent30_REFURBISHED_gte": Integer,
	"deltaPercent30_NEW_FBM_SHIPPING_lte": Integer,
	"deltaPercent30_NEW_FBM_SHIPPING_gte": Integer,
	"deltaPercent30_LIGHTNING_DEAL_lte": Integer,
	"deltaPercent30_LIGHTNING_DEAL_gte": Integer,
	"deltaPercent30_WAREHOUSE_lte": Integer,
	"deltaPercent30_WAREHOUSE_gte": Integer,
	"deltaPercent30_NEW_FBA_lte": Integer,
	"deltaPercent30_NEW_FBA_gte": Integer,
	"deltaPercent30_COUNT_NEW_lte": Integer,
	"deltaPercent30_COUNT_NEW_gte": Integer,
	"deltaPercent30_COUNT_USED_lte": Integer,
	"deltaPercent30_COUNT_USED_gte": Integer,
	"deltaPercent30_COUNT_REFURBISHED_lte": Integer,
	"deltaPercent30_COUNT_REFURBISHED_gte": Integer,
	"deltaPercent30_COUNT_COLLECTIBLE_lte": Integer,
	"deltaPercent30_COUNT_COLLECTIBLE_gte": Integer,
	"deltaPercent30_RATING_lte": Integer,
	"deltaPercent30_RATING_gte": Integer,
	"deltaPercent30_COUNT_REVIEWS_lte": Integer,
	"deltaPercent30_COUNT_REVIEWS_gte": Integer,
	"deltaPercent30_BUY_BOX_SHIPPING_lte": Integer,
	"deltaPercent30_BUY_BOX_SHIPPING_gte": Integer,
	"deltaPercent30_USED_NEW_SHIPPING_lte": Integer,
	"deltaPercent30_USED_NEW_SHIPPING_gte": Integer,
	"deltaPercent30_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"deltaPercent30_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"deltaPercent30_USED_GOOD_SHIPPING_lte": Integer,
	"deltaPercent30_USED_GOOD_SHIPPING_gte": Integer,
	"deltaPercent30_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"deltaPercent30_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"deltaPercent30_REFURBISHED_SHIPPING_lte": Integer,
	"deltaPercent30_REFURBISHED_SHIPPING_gte": Integer,
	"deltaPercent30_TRADE_IN_lte": Integer,
	"deltaPercent30_TRADE_IN_gte": Integer,
	"deltaLast_AMAZON_lte": Integer,
	"deltaLast_AMAZON_gte": Integer,
	"deltaLast_NEW_lte": Integer,
	"deltaLast_NEW_gte": Integer,
	"deltaLast_USED_lte": Integer,
	"deltaLast_USED_gte": Integer,
	"deltaLast_SALES_lte": Integer,
	"deltaLast_SALES_gte": Integer,
	"deltaLast_LISTPRICE_lte": Integer,
	"deltaLast_LISTPRICE_gte": Integer,
	"deltaLast_COLLECTIBLE_lte": Integer,
	"deltaLast_COLLECTIBLE_gte": Integer,
	"deltaLast_REFURBISHED_lte": Integer,
	"deltaLast_REFURBISHED_gte": Integer,
	"deltaLast_NEW_FBM_SHIPPING_lte": Integer,
	"deltaLast_NEW_FBM_SHIPPING_gte": Integer,
	"deltaLast_LIGHTNING_DEAL_lte": Integer,
	"deltaLast_LIGHTNING_DEAL_gte": Integer,
	"deltaLast_WAREHOUSE_lte": Integer,
	"deltaLast_WAREHOUSE_gte": Integer,
	"deltaLast_NEW_FBA_lte": Integer,
	"deltaLast_NEW_FBA_gte": Integer,
	"deltaLast_COUNT_NEW_lte": Integer,
	"deltaLast_COUNT_NEW_gte": Integer,
	"deltaLast_COUNT_USED_lte": Integer,
	"deltaLast_COUNT_USED_gte": Integer,
	"deltaLast_COUNT_REFURBISHED_lte": Integer,
	"deltaLast_COUNT_REFURBISHED_gte": Integer,
	"deltaLast_COUNT_COLLECTIBLE_lte": Integer,
	"deltaLast_COUNT_COLLECTIBLE_gte": Integer,
	"deltaLast_RATING_lte": Integer,
	"deltaLast_RATING_gte": Integer,
	"deltaLast_COUNT_REVIEWS_lte": Integer,
	"deltaLast_COUNT_REVIEWS_gte": Integer,
	"deltaLast_BUY_BOX_SHIPPING_lte": Integer,
	"deltaLast_BUY_BOX_SHIPPING_gte": Integer,
	"deltaLast_USED_NEW_SHIPPING_lte": Integer,
	"deltaLast_USED_NEW_SHIPPING_gte": Integer,
	"deltaLast_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"deltaLast_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"deltaLast_USED_GOOD_SHIPPING_lte": Integer,
	"deltaLast_USED_GOOD_SHIPPING_gte": Integer,
	"deltaLast_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"deltaLast_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"deltaLast_REFURBISHED_SHIPPING_lte": Integer,
	"deltaLast_REFURBISHED_SHIPPING_gte": Integer,
	"deltaLast_TRADE_IN_lte": Integer,
	"deltaLast_TRADE_IN_gte": Integer,
	"avg180_AMAZON_lte": Integer,
	"avg180_AMAZON_gte": Integer,
	"avg180_NEW_lte": Integer,
	"avg180_NEW_gte": Integer,
	"avg180_USED_lte": Integer,
	"avg180_USED_gte": Integer,
	"avg180_SALES_lte": Integer,
	"avg180_SALES_gte": Integer,
	"avg180_LISTPRICE_lte": Integer,
	"avg180_LISTPRICE_gte": Integer,
	"avg180_COLLECTIBLE_lte": Integer,
	"avg180_COLLECTIBLE_gte": Integer,
	"avg180_REFURBISHED_lte": Integer,
	"avg180_REFURBISHED_gte": Integer,
	"avg180_NEW_FBM_SHIPPING_lte": Integer,
	"avg180_NEW_FBM_SHIPPING_gte": Integer,
	"avg180_LIGHTNING_DEAL_lte": Integer,
	"avg180_LIGHTNING_DEAL_gte": Integer,
	"avg180_WAREHOUSE_lte": Integer,
	"avg180_WAREHOUSE_gte": Integer,
	"avg180_NEW_FBA_lte": Integer,
	"avg180_NEW_FBA_gte": Integer,
	"avg180_COUNT_NEW_lte": Integer,
	"avg180_COUNT_NEW_gte": Integer,
	"avg180_COUNT_USED_lte": Integer,
	"avg180_COUNT_USED_gte": Integer,
	"avg180_COUNT_REFURBISHED_lte": Integer,
	"avg180_COUNT_REFURBISHED_gte": Integer,
	"avg180_COUNT_COLLECTIBLE_lte": Integer,
	"avg180_COUNT_COLLECTIBLE_gte": Integer,
	"avg180_RATING_lte": Integer,
	"avg180_RATING_gte": Integer,
	"avg180_COUNT_REVIEWS_lte": Integer,
	"avg180_COUNT_REVIEWS_gte": Integer,
	"avg180_BUY_BOX_SHIPPING_lte": Integer,
	"avg180_BUY_BOX_SHIPPING_gte": Integer,
	"avg180_USED_NEW_SHIPPING_lte": Integer,
	"avg180_USED_NEW_SHIPPING_gte": Integer,
	"avg180_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"avg180_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"avg180_USED_GOOD_SHIPPING_lte": Integer,
	"avg180_USED_GOOD_SHIPPING_gte": Integer,
	"avg180_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"avg180_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"avg180_REFURBISHED_SHIPPING_lte": Integer,
	"avg180_REFURBISHED_SHIPPING_gte": Integer,
	"avg180_TRADE_IN_lte": Integer,
	"avg180_TRADE_IN_gte": Integer,
	"avg90_AMAZON_lte": Integer,
	"avg90_AMAZON_gte": Integer,
	"avg90_NEW_lte": Integer,
	"avg90_NEW_gte": Integer,
	"avg90_USED_lte": Integer,
	"avg90_USED_gte": Integer,
	"avg90_SALES_lte": Integer,
	"avg90_SALES_gte": Integer,
	"avg90_LISTPRICE_lte": Integer,
	"avg90_LISTPRICE_gte": Integer,
	"avg90_COLLECTIBLE_lte": Integer,
	"avg90_COLLECTIBLE_gte": Integer,
	"avg90_REFURBISHED_lte": Integer,
	"avg90_REFURBISHED_gte": Integer,
	"avg90_NEW_FBM_SHIPPING_lte": Integer,
	"avg90_NEW_FBM_SHIPPING_gte": Integer,
	"avg90_LIGHTNING_DEAL_lte": Integer,
	"avg90_LIGHTNING_DEAL_gte": Integer,
	"avg90_WAREHOUSE_lte": Integer,
	"avg90_WAREHOUSE_gte": Integer,
	"avg90_NEW_FBA_lte": Integer,
	"avg90_NEW_FBA_gte": Integer,
	"avg90_COUNT_NEW_lte": Integer,
	"avg90_COUNT_NEW_gte": Integer,
	"avg90_COUNT_USED_lte": Integer,
	"avg90_COUNT_USED_gte": Integer,
	"avg90_COUNT_REFURBISHED_lte": Integer,
	"avg90_COUNT_REFURBISHED_gte": Integer,
	"avg90_COUNT_COLLECTIBLE_lte": Integer,
	"avg90_COUNT_COLLECTIBLE_gte": Integer,
	"avg90_RATING_lte": Integer,
	"avg90_RATING_gte": Integer,
	"avg90_COUNT_REVIEWS_lte": Integer,
	"avg90_COUNT_REVIEWS_gte": Integer,
	"avg90_BUY_BOX_SHIPPING_lte": Integer,
	"avg90_BUY_BOX_SHIPPING_gte": Integer,
	"avg90_USED_NEW_SHIPPING_lte": Integer,
	"avg90_USED_NEW_SHIPPING_gte": Integer,
	"avg90_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"avg90_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"avg90_USED_GOOD_SHIPPING_lte": Integer,
	"avg90_USED_GOOD_SHIPPING_gte": Integer,
	"avg90_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"avg90_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"avg90_REFURBISHED_SHIPPING_lte": Integer,
	"avg90_REFURBISHED_SHIPPING_gte": Integer,
	"avg90_TRADE_IN_lte": Integer,
	"avg90_TRADE_IN_gte": Integer,
	"avg30_AMAZON_lte": Integer,
	"avg30_AMAZON_gte": Integer,
	"avg30_NEW_lte": Integer,
	"avg30_NEW_gte": Integer,
	"avg30_USED_lte": Integer,
	"avg30_USED_gte": Integer,
	"avg30_SALES_lte": Integer,
	"avg30_SALES_gte": Integer,
	"avg30_LISTPRICE_lte": Integer,
	"avg30_LISTPRICE_gte": Integer,
	"avg30_COLLECTIBLE_lte": Integer,
	"avg30_COLLECTIBLE_gte": Integer,
	"avg30_REFURBISHED_lte": Integer,
	"avg30_REFURBISHED_gte": Integer,
	"avg30_NEW_FBM_SHIPPING_lte": Integer,
	"avg30_NEW_FBM_SHIPPING_gte": Integer,
	"avg30_LIGHTNING_DEAL_lte": Integer,
	"avg30_LIGHTNING_DEAL_gte": Integer,
	"avg30_WAREHOUSE_lte": Integer,
	"avg30_WAREHOUSE_gte": Integer,
	"avg30_NEW_FBA_lte": Integer,
	"avg30_NEW_FBA_gte": Integer,
	"avg30_COUNT_NEW_lte": Integer,
	"avg30_COUNT_NEW_gte": Integer,
	"avg30_COUNT_USED_lte": Integer,
	"avg30_COUNT_USED_gte": Integer,
	"avg30_COUNT_REFURBISHED_lte": Integer,
	"avg30_COUNT_REFURBISHED_gte": Integer,
	"avg30_COUNT_COLLECTIBLE_lte": Integer,
	"avg30_COUNT_COLLECTIBLE_gte": Integer,
	"avg30_RATING_lte": Integer,
	"avg30_RATING_gte": Integer,
	"avg30_COUNT_REVIEWS_lte": Integer,
	"avg30_COUNT_REVIEWS_gte": Integer,
	"avg30_BUY_BOX_SHIPPING_lte": Integer,
	"avg30_BUY_BOX_SHIPPING_gte": Integer,
	"avg30_USED_NEW_SHIPPING_lte": Integer,
	"avg30_USED_NEW_SHIPPING_gte": Integer,
	"avg30_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"avg30_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"avg30_USED_GOOD_SHIPPING_lte": Integer,
	"avg30_USED_GOOD_SHIPPING_gte": Integer,
	"avg30_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"avg30_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"avg30_REFURBISHED_SHIPPING_lte": Integer,
	"avg30_REFURBISHED_SHIPPING_gte": Integer,
	"avg30_TRADE_IN_lte": Integer,
	"avg30_TRADE_IN_gte": Integer,
	"avg365_AMAZON_lte": Integer,
	"avg365_AMAZON_gte": Integer,
	"avg365_BUY_BOX_SHIPPING_lte": Integer,
	"avg365_BUY_BOX_SHIPPING_gte": Integer,
	"avg365_BUY_BOX_USED_SHIPPING_lte": Integer,
	"avg365_BUY_BOX_USED_SHIPPING_gte": Integer,
	"avg365_COLLECTIBLE_lte": Integer,
	"avg365_COLLECTIBLE_gte": Integer,
	"avg365_COUNT_COLLECTIBLE_lte": Integer,
	"avg365_COUNT_COLLECTIBLE_gte": Integer,
	"avg365_COUNT_NEW_lte": Integer,
	"avg365_COUNT_NEW_gte": Integer,
	"avg	365_COUNT_REFURBISHED_lte": Integer,
	"avg365_COUNT_REFURBISHED_gte": Integer,
	"avg365_COUNT_REVIEWS_lte": Integer,
	"avg365_COUNT_REVIEWS_gte": Integer,
	"avg365_COUNT_USED_lte": Integer,
	"avg365_COUNT_USED_gte": Integer,
	"avg365_EBAY_NEW_SHIPPING_lte": Integer,
	"avg365_EBAY_NEW_SHIPPING_gte": Integer,
	"avg365_EBAY_USED_SHIPPING_lte": Integer,
	"avg365_EBAY_USED_SHIPPING_gte": Integer,
	"avg365_LIGHTNING_DEAL_lte": Integer,
	"avg365_LIGHTNING_DEAL_gte": Integer,
	"avg365_LISTPRICE_lte": Integer,
	"avg365_LISTPRICE_gte": Integer,
	"avg365_NEW_lte": Integer,
	"avg365_NEW_gte": Integer,
	"avg365_NEW_FBA_lte": Integer,
	"avg365_NEW_FBA_gte": Integer,
	"avg365_NEW_FBM_SHIPPING_lte": Integer,
	"avg365_NEW_FBM_SHIPPING_gte": Integer,
	"avg365_PRIME_EXCL_lte": Integer,
	"avg365_PRIME_EXCL_gte": Integer,
	"avg365_RATING_lte": Integer,
	"avg365_RATING_gte": Integer,
	"avg365_REFURBISHED_lte": Integer,
	"avg365_REFURBISHED_gte": Integer,
	"avg365_REFURBISHED_SHIPPING_lte": Integer,
	"avg365_REFURBISHED_SHIPPING_gte": Integer,
	"avg365_RENT_lte": Integer,
	"avg365_RENT_gte": Integer,
	"avg365_SALES_lte": Integer,
	"avg365_SALES_gte": Integer,
	"avg365_TRADE_IN_lte": Integer,
	"avg365_TRADE_IN_gte": Integer,
	"avg365_USED_lte": Integer,
	"avg365_USED_gte": Integer,
	"avg365_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"avg365_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"avg365_USED_GOOD_SHIPPING_lte": Integer,
	"avg365_USED_GOOD_SHIPPING_gte": Integer,
	"avg365_USED_NEW_SHIPPING_lte": Integer,
	"avg365_USED_NEW_SHIPPING_gte": Integer,
	"avg365_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"avg365_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"avg365_WAREHOUSE_lte": Integer,
	"avg365_WAREHOUSE_gte": Integer,

	"lastPriceChange_AMAZON_lte": Integer,
	"lastPriceChange_AMAZON_gte": Integer,
	"lastPriceChange_NEW_lte": Integer,
	"lastPriceChange_NEW_gte": Integer,
	"lastPriceChange_USED_lte": Integer,
	"lastPriceChange_USED_gte": Integer,
	"lastPriceChange_SALES_lte": Integer,
	"lastPriceChange_SALES_gte": Integer,
	"lastPriceChange_LISTPRICE_lte": Integer,
	"lastPriceChange_LISTPRICE_gte": Integer,
	"lastPriceChange_COLLECTIBLE_lte": Integer,
	"lastPriceChange_COLLECTIBLE_gte": Integer,
	"lastPriceChange_REFURBISHED_lte": Integer,
	"lastPriceChange_REFURBISHED_gte": Integer,
	"lastPriceChange_NEW_FBM_SHIPPING_lte": Integer,
	"lastPriceChange_NEW_FBM_SHIPPING_gte": Integer,
	"lastPriceChange_LIGHTNING_DEAL_lte": Integer,
	"lastPriceChange_LIGHTNING_DEAL_gte": Integer,
	"lastPriceChange_WAREHOUSE_lte": Integer,
	"lastPriceChange_WAREHOUSE_gte": Integer,
	"lastPriceChange_NEW_FBA_lte": Integer,
	"lastPriceChange_NEW_FBA_gte": Integer,
	"lastPriceChange_COUNT_NEW_lte": Integer,
	"lastPriceChange_COUNT_NEW_gte": Integer,
	"lastPriceChange_COUNT_USED_lte": Integer,
	"lastPriceChange_COUNT_USED_gte": Integer,
	"lastPriceChange_COUNT_REFURBISHED_lte": Integer,
	"lastPriceChange_COUNT_REFURBISHED_gte": Integer,
	"lastPriceChange_COUNT_COLLECTIBLE_lte": Integer,
	"lastPriceChange_COUNT_COLLECTIBLE_gte": Integer,
	"lastPriceChange_RATING_lte": Integer,
	"lastPriceChange_RATING_gte": Integer,
	"lastPriceChange_COUNT_REVIEWS_lte": Integer,
	"lastPriceChange_COUNT_REVIEWS_gte": Integer,
	"lastPriceChange_BUY_BOX_SHIPPING_lte": Integer,
	"lastPriceChange_BUY_BOX_SHIPPING_gte": Integer,
	"lastPriceChange_USED_NEW_SHIPPING_lte": Integer,
	"lastPriceChange_USED_NEW_SHIPPING_gte": Integer,
	"lastPriceChange_USED_VERY_GOOD_SHIPPING_lte": Integer,
	"lastPriceChange_USED_VERY_GOOD_SHIPPING_gte": Integer,
	"lastPriceChange_USED_GOOD_SHIPPING_lte": Integer,
	"lastPriceChange_USED_GOOD_SHIPPING_gte": Integer,
	"lastPriceChange_USED_ACCEPTABLE_SHIPPING_lte": Integer,
	"lastPriceChange_USED_ACCEPTABLE_SHIPPING_gte": Integer,
	"lastPriceChange_REFURBISHED_SHIPPING_lte": Integer,
	"lastPriceChange_REFURBISHED_SHIPPING_gte": Integer,
	"lastPriceChange_EBAY_NEW_SHIPPING_lte": Integer,
	"lastPriceChange_EBAY_NEW_SHIPPING_gte": Integer,
	"lastPriceChange_EBAY_USED_SHIPPING_lte": Integer,
	"lastPriceChange_EBAY_USED_SHIPPING_gte": Integer,
	"lastPriceChange_TRADE_IN_lte": Integer,
	"lastPriceChange_TRADE_IN_gte": Integer,
	"lastPriceChange_RENT_lte": Integer,
	"lastPriceChange_RENT_gte": Integer,
	"lastPriceChange_BUY_BOX_USED_SHIPPING_lte": Integer,
	"lastPriceChange_BUY_BOX_USED_SHIPPING_gte": Integer,
	"lastPriceChange_PRIME_EXCL_lte": Integer,
	"lastPriceChange_PRIME_EXCL_gte": Integer,

	"backInStock_AMAZON": Boolean,
	"backInStock_NEW": Boolean,
	"backInStock_USED": Boolean,
	"backInStock_SALES": Boolean,
	"backInStock_LISTPRICE": Boolean,
	"backInStock_COLLECTIBLE": Boolean,
	"backInStock_REFURBISHED": Boolean,
	"backInStock_NEW_FBM_SHIPPING": Boolean,
	"backInStock_LIGHTNING_DEAL": Boolean,
	"backInStock_WAREHOUSE": Boolean,
	"backInStock_NEW_FBA": Boolean,
	"backInStock_COUNT_NEW": Boolean,
	"backInStock_COUNT_USED": Boolean,
	"backInStock_COUNT_REFURBISHED": Boolean,
	"backInStock_COUNT_COLLECTIBLE": Boolean,
	"backInStock_RATING": Boolean,
	"backInStock_COUNT_REVIEWS": Boolean,
	"backInStock_BUY_BOX_SHIPPING": Boolean,
	"backInStock_USED_NEW_SHIPPING": Boolean,
	"backInStock_USED_VERY_GOOD_SHIPPING": Boolean,
	"backInStock_USED_GOOD_SHIPPING": Boolean,
	"backInStock_USED_ACCEPTABLE_SHIPPING": Boolean,
	"backInStock_REFURBISHED_SHIPPING": Boolean,
	"backInStock_TRADE_IN": Boolean,

	"isLowest_AMAZON": Boolean,
	"isLowest_BUY_BOX_SHIPPING": Boolean,
	"isLowest_BUY_BOX_USED_SHIPPING": Boolean,
	"isLowest_COLLECTIBLE": Boolean,
	"isLowest_COUNT_COLLECTIBLE": Boolean,
	"isLowest_COUNT_NEW": Boolean,
	"isLowest_COUNT_REFURBISHED": Boolean,
	"isLowest_COUNT_REVIEWS": Boolean,
	"isLowest_COUNT_USED": Boolean,
	"isLowest_EBAY_NEW_SHIPPING": Boolean,
	"isLowest_EBAY_USED_SHIPPING": Boolean,
	"isLowest_LIGHTNING_DEAL": Boolean,
	"isLowest_LISTPRICE": Boolean,
	"isLowest_NEW": Boolean,
	"isLowest_NEW_FBA": Boolean,
	"isLowest_NEW_FBM_SHIPPING": Boolean,
	"isLowest_PRIME_EXCL": Boolean,
	"isLowest_RATING": Boolean,
	"isLowest_REFURBISHED": Boolean,
	"isLowest_REFURBISHED_SHIPPING": Boolean,
	"isLowest_RENT": Boolean,
	"isLowest_SALES": Boolean,
	"isLowest_TRADE_IN": Boolean,
	"isLowest_USED": Boolean,
	"isLowest_USED_ACCEPTABLE_SHIPPING": Boolean,
	"isLowest_USED_GOOD_SHIPPING": Boolean,
	"isLowest_USED_NEW_SHIPPING": Boolean,
	"isLowest_USED_VERY_GOOD_SHIPPING": Boolean,
	"isLowest_WAREHOUSE": Boolean,
	"isLowest90_AMAZON": Boolean,
	"isLowest90_BUY_BOX_SHIPPING": Boolean,
	"isLowest90_BUY_BOX_USED_SHIPPING": Boolean,
	"isLowest90_COLLECTIBLE": Boolean,
	"isLowest90_COUNT_COLLECTIBLE": Boolean,
	"isLowest90_COUNT_NEW": Boolean,
	"isLowest90_COUNT_REFURBISHED": Boolean,
	"isLowest90_COUNT_REVIEWS": Boolean,
	"isLowest90_COUNT_USED": Boolean,
	"isLowest90_EBAY_NEW_SHIPPING": Boolean,
	"isLowest90_EBAY_USED_SHIPPING": Boolean,
	"isLowest90_LIGHTNING_DEAL": Boolean,
	"isLowest90_LISTPRICE": Boolean,
	"isLowest90_NEW": Boolean,
	"isLowest90_NEW_FBA": Boolean,
	"isLowest90_NEW_FBM_SHIPPING": Boolean,
	"isLowest90_PRIME_EXCL": Boolean,
	"isLowest90_RATING": Boolean,
	"isLowest90_REFURBISHED": Boolean,
	"isLowest90_REFURBISHED_SHIPPING": Boolean,
	"isLowest90_RENT": Boolean,
	"isLowest90_SALES": Boolean,
	"isLowest90_TRADE_IN": Boolean,
	"isLowest90_USED": Boolean,
	"isLowest90_USED_ACCEPTABLE_SHIPPING": Boolean,
	"isLowest90_USED_GOOD_SHIPPING": Boolean,
	"isLowest90_USED_NEW_SHIPPING": Boolean,
	"isLowest90_USED_VERY_GOOD_SHIPPING": Boolean,
	"isLowest90_WAREHOUSE": Boolean
}
```



#### Optional Parameter

`stats` - **Token Cost:** 30 tokens + 1 token for every 1 000 000 products returned by the *query as a whole* (not just the current page). If specified and set to `1`, the response will include a [Search Insights Object](https://discuss.keepa.com/t/search-insights-object/18199).

**Example:** `&stats=1`

------

#### Paging

*Paging is optional; by default, up to 50 results are provided.*

- **page**:
  Most queries have more than 50 results (the minimum page size). To retrieve additional results, iterate the `page` parameter while keeping all other parameters identical. Start with `page` 0 and stop when the response contains fewer than 50 results. Each response also includes the `totalResults` field, indicating the number of matched products. When requesting a `page` other than 0, the combination of `page` and `perPage` must not exceed 10,000 results.

  *Example:* `0`

- **perPage**:
  Specifies the number of results to retrieve per page. The default and minimum values are 50 ASINs. If `page` is **0**, `perPage` can be as large as 10,000. If a `page` other than 0 is requested, the combination of `page` and `perPage` must not exceed 10,000 results.

  **Note:** Requesting large lists may consume more tokens than are available in your bucket, causing your balance to go negative. Use with caution.

#### Sorting

*Sorting is optional; by default, results are sorted ascending by current sales rank.*

- **sort**:
  Can include up to three sorting criteria. Use a two-dimensional array where each entry is in the format:

  `[fieldName, sortDirection]`

  - **fieldName**: Any filter from the list below that is either a String or Integer. The `fieldName` must not include `_lte` or `_gte`.
  - **sortDirection**: Use `"asc"` for ascending or `"desc"` for descending.

  *Example:* `[ ["current_SALES", "asc"] ]`

------

#### Filters

##### *All filters are optional; the query is valid as long as at least one filter is specified.*

The following fields act as filters. Only products that **exactly** match all filters will be returned by the query. All string filters are case insensitive and can be used as exclusion filters by using the prefix ‘✜’. Filters ending in “_gte” restrict the output to values “Greater than or equal” to the specified value, while “_lte” means “Less than or equal”.

- `rootCategory`:
  Only include products listed in these root-categories. Array with up to 50 [category node ids](https://discuss.keepa.com/t/category-object/115).
  Example: *[562066]*

- `categories_include`:
  Only include products listed directly in these sub-categories. Array with up to 50 [category node ids](https://discuss.keepa.com/t/category-object/115).
  Example: [3010075031,12950651,355007011]

- `categories_exclude`:
  Exclude products listed directly in these sub-categories. Array with up to 50 [category node ids](https://discuss.keepa.com/t/category-object/115).
  Example: [77028031,186606]

- `salesRankReference`:
  [Category node id](https://discuss.keepa.com/t/category-object/115) of the product’s salesRankReference category.
  Example: *562066*

- `title`:
  Title of the product. Works on a keyword basis, meaning the product’s title must contain the specified string’s keywords, separated by white space. Supports up to 50 keywords. The search is case-insensitive. Partial keyword matches are not supported.
  Examples:

  - *Digital Camera Canon*: Title must contain all three keywords, in any order or position.
  - *“Digital Camera” Canon*: Title must contain the keyword *Digital Camera* and *Canon*.
  - *-digital camera*: Title must *not* contain the keyword *digital* and must contain *camera*.

- `productType`:
  Determines what data is available for the product. Possible filter values:

  - **0** - STANDARD: everything accessible
  - **1** - DOWNLOADABLE: no marketplace/3rd party price data
  - **2** - EBOOK: No marketplace offers data
  - **5** - VARIATION_PARENT: product is a parent ASIN. Only sales rank and `variationCSV` is set.

- `singleVariation`:
  If set to **true**, only one variation of a product will be returned.

- `hasParentASIN`:
  Whether or not the product has a parent ASIN.

- `availabilityAmazon`:
  Availability of the Amazon offer. Possible values:

  - -1: no Amazon offer exists
  - 0: Amazon offer is in stock and shippable
  - 1: Amazon offer is currently not in stock, but will be in the future (pre-order)
  - 2: Amazon offer availability is “unknown”
  - 3: Amazon offer is currently not in stock, but will be in the future (back-order)
  - 4: Amazon offer shipping is delayed - see “availabilityAmazonDelay” for more details

- `returnRate`:
  The customer return rate for a product. The possible values are:

  - *1*: The product has a low return rate.
  - *2*: The product has a high return rate.

- `hasReviews`:
  Whether or not the product has reviews.

- `manufacturer`:
  Names of manufacturers. Example: *Canon*

- `brand`:
  Names of brands. Example: *Canon*

- `productGroup`:
  Names of product groups. Example: *apparel*

- `model`:
  Names of models. Example: *2016*

- `color`:
  Names of colors. Example: *black*

- `size`:
  Names of sizes. Example: *large*

- `edition`:
  Names of editions. Example: *first edition*

- `format`:
  Names of formats. Example: *cd-rom*

- `author`:
  Names of authors. Example: *anonymous*

- `binding`:
  Names of bindings. Example: *paperback*

- `genre`:
  Names of genres. Example: *horror*

- `languages`:
  Languages available for the item. Example: *english*

- `publisher`:
  Publisher of the item. Example: *penguin books*

- `platform`:
  Platforms the item is available on. Example: *windows*

- `activeIngredients`:
  Active ingredients in the product. Example: *aloe*

- `specialIngredients`:
  Special or additional ingredients in the product. Example: *fragrance-free*

- `itemTypeKeyword`:
  Keywords describing the type of item. Example: _ road-running-shoes_

- `targetAudienceKeyword`:
  Keywords indicating the target audience. Example: *dogs*

- `itemForm`:
  The form of the item. Example: *liquid*

- `scent`:
  Scent of the product, if applicable. Example: *lavender*

- `unitType`:
  Type of unit measurement used. Example: *count*

- `pattern`:
  Pattern design of the item. Example: *striped*

- `style`:
  Style or design aesthetic of the item. Example: *modern*

- `material`:
  Material composition of the item. Example: *cotton*

- `frequentlyBoughtTogether`:
  Specify an ASIN to retrieve products that are often bought together with it. Example: *B06XFTZGV5*

- `couponOneTimeAbsolute_lte`:
  Maximum absolute value for one-time coupons. Example: *50*

- `couponOneTimeAbsolute_gte`:
  Minimum absolute value for one-time coupons. Example: *10*

- `couponOneTimePercent_lte`:
  Maximum percentage value for one-time coupons. Example: *20*

- `couponOneTimePercent_gte`:
  Minimum percentage value for one-time coupons. Example: *5*

- `couponSNSPercent_lte`:
  Maximum percentage value for SNS coupons. Example: *15*

- `couponSNSPercent_gte`:
  Minimum percentage value for SNS coupons. Example: *3*

- `flipability30_lte`:
  Maximum flipability score over 30 days. Example: *80*

- `flipability30_gte`:
  Minimum flipability score over 30 days. Example: *20*

- `flipability90_lte`:
  Maximum flipability score over 90 days. Example: *85*

- `flipability90_gte`:
  Minimum flipability score over 90 days. Example: *25*

- `flipability365_lte`:
  Maximum flipability score over 365 days. Example: *90*

- `flipability365_gte`:
  Minimum flipability score over 365 days. Example: *30*

- `businessDiscount_lte`:
  Maximum business discount available. Example: *15*

- `businessDiscount_gte`:
  Minimum business discount available. Example: *5*

- `batteriesRequired`:
  If the item requires batteries. Example: *true*

- `batteriesIncluded`:
  If batteries are included with the item. Example: *false*

- `isMerchOnDemand`:
  If the product is a MerchOnDemand. Example: *true*

- `hasMainVideo`:
  If the item has a main promotional video, which part of the product image carousel. Example: *true*

- `hasAPlus`:
  If the item has A+ content. Example: *false*

- `hasAPlusFromManufacturer`:
  If the A+ content is provided by the manufacturer or vendor. Example: *true*

- `videoCount_lte`:
  Maximum number of videos associated with the item. Example: *10*

- `videoCount_gte`:
  Minimum number of videos associated with the item. Example: *1*

- `brandStoreName`:
  Name of the brand’s store. Example: *[“techworld”]*

- `brandStoreUrlName`:
  URL-friendly name of the brand’s store. Example: *[“techworld-store”]*

- `buyBoxIsAmazon`:
  If the Buy Box is held by Amazon. Example: *true*

- `buyBoxIsFBA`:
  If the Buy Box is fulfilled by Amazon (FBA). Example: *false*

- `buyBoxIsUnqualified`:
  If the Buy Box is unqualified. Example: *false*

- `buyBoxSellerId`:
  Seller IDs in the Buy Box. Example: *["ATVPDKIKX0DER]*

- `buyBoxUsedCondition`:
  The offer sub-condition of the **used** buy box. Example: *[2, 3]*

  | Value | Condition         |
  | :---- | :---------------- |
  | 2     | Used - Like New   |
  | 3     | Used - Very Good  |
  | 4     | Used - Good       |
  | 5     | Used - Acceptable |

- `buyBoxUsedIsFBA`:
  If the Used Buy Box is fulfilled by Amazon. Example: *true*

- `buyBoxUsedSellerId`:
  Seller IDs for used items eligible for the Buy Box. Example: *[“ATVPDKIKX0DER”]*

- `sellerIds`:
  List of seller IDs offering the item. Example: *[“ATVPDKIKX0DER”]*

- `sellerIdsLowestFBA`:
  Seller IDs offering the lowest price via FBA. Example: *[“ATVPDKIKX0DER”]*

- `sellerIdsLowestFBM`:
  Seller IDs offering the lowest price via FBM. Example: *[“ATVPDKIKX0DER”]*

- `partNumber`:
  Names of part numbers. Example: *DSC-H300/BM-RB*

- `variationReviewCount_lte`:
  Maximum number of reviews specific to a variation. Example: *100*

- `variationReviewCount_gte`:
  Minimum number of reviews specific to a variation. Example: *10*

- `variationRatingCount_lte`:
  Maximum number of ratings specific to a variation. Example: *200*

- `variationRatingCount_gte`:
  Minimum number of ratings specific to a variation. Example: *20*

- `deltaPercent90_monthlySold_lte`:
  Maximum percentage change in monthly sales over the last 90 days. Example: *15*

- `deltaPercent90_monthlySold_gte`:
  Minimum percentage change in monthly sales over the last 90 days. Example: *-10*

- `outOfStockCountAmazon30_lte`:
  Maximum number of times the item was out of stock on Amazon in the last 30 days. Example: *2*

- `outOfStockCountAmazon30_gte`:
  Minimum number of times the item was out of stock on Amazon in the last 30 days. Example: *1*

- `outOfStockCountAmazon90_lte`:
  Maximum number of times the item was out of stock on Amazon in the last 90 days. Example: *5*

- `outOfStockCountAmazon90_gte`:
  Minimum number of times the item was out of stock on Amazon in the last 90 days. Example: *3*

- `lastPriceChange` [_lte, _gte]:
  The last time a price change (any price type) was registered, in **Keepa Time minutes**.

- `lastPriceChange` [_PriceType] [_lte, _gte]:
  The last time a price change of this price type was registered, in **Keepa Time minutes**.

- `trackingSince` [_lte, _gte]:
  Indicates the time we started tracking this product, in **Keepa Time minutes**.
  Example: *3411319*

- `lightningEnd` [_lte, _gte]:
  Find current and upcoming lightning deals that end within the defined range. In **Keepa Time minutes**.

- `packageHeight` [_lte, _gte]:
  The package’s height in millimeters. Example: *144*

- `packageLength` [_lte, _gte]:
  The package’s length in millimeters. Example: *144*

- `packageWidth` [_lte, _gte]:
  The package’s width in millimeters. Example: *144*

- `packageWeight` [_lte, _gte]:
  The package’s weight in grams. Example: *1500 (= 1.5 kg)*

- `itemHeight` [_lte, _gte]:
  The item’s height in millimeters. Example: *144*

- `itemLength` [_lte, _gte]:
  The item’s length in millimeters. Example: *144*

- `itemWidth` [_lte, _gte]:
  The item’s width in millimeters. Example: *144*

- `itemWeight` [_lte, _gte]:
  The item’s weight in grams. Example: *1500 (= 1.5 kg)*

- `outOfStockPercentage90` [_lte, _gte]:
  90-day Amazon out-of-stock percentage.
  Examples: 0 = never out of stock, 100 = out of stock 100% of the time, 25 = out of stock 25% of the time

- `variationCount` [_lte, _gte]:
  The number of variations of this product. Example: *1*

- `imageCount` [_lte, _gte]:
  The number of images of this product. Example: *1*

- `buyBoxStatsAmazon` [30, 90, 180, 365] [_lte, _gte]:
  The percentage the Amazon offer held the Buy Box in the given interval. Example: *30*

- `buyBoxStatsTopSeller` [30, 90, 180, 365] [_lte, _gte]:
  Buy Box Share % of the Seller with highest % won (Amazon incl.). Example: *30*

- `buyBoxStatsSellerCount` [30, 90, 180, 365] [_lte, _gte]:
  Number of sellers with buy box ownership in the interval. Example: *2*

- `numberOfItems` [_lte, _gte]:
  The number of items of this product. Example: *1*

- `numberOfPages` [_lte, _gte]:
  The number of pages of this product. Example: *514*

- `publicationDate` [_lte, _gte]:
  The item’s publication date, in **Keepa Time minutes**. Example: *3411319*

- `releaseDate` [_lte, _gte]:
  The item’s release date, in **Keepa Time minutes**. Example: *3411319*

- `monthlySold` [_lte, _gte]:
  How often this product was bought in the past month. This field represents the *bought past month* metric found on Amazon search result pages. It is not an estimate. *Undefined* if it has no value. Most ASINs do not have this value set. The value is variation specific.
  Example: *1000* - the ASIN was bought at least 1000 times in the past month.

- `lastOffersUpdate` [_lte, _gte]:
  The time when the offers were last updated (see the product request’s offers parameter), in **Keepa Time minutes**. Can be used to retrieve only products with fresh offers-related data.
  Example: *3411319*

- `isPrimeExclusive`:
  A Prime exclusive offer can only be ordered if the buyer has an active Prime subscription. Example: *true*

- `isHazMat`:
  Indicates whether the product is classified as hazardous material (HazMat). Example: *true*

- `isHeatSensitive`:
  Indicates whether the product is classified as heat sensitive (e.g. meltable). Example: *true*

- `isAdultProduct`:
  Indicates if the item is considered to be for adults only. Example: *true*

- `isEligibleForTradeIn`:
  Whether or not the product is eligible for trade-in. Example: *true*

- `isEligibleForSuperSaverShipping`:
  Whether or not the product is eligible for super saver shipping by Amazon. Example: *true*

- `isSNS`:
  If the product’s Buy Box is available for [subscribe and save](https://www.amazon.com/b?node=5856181011). Example: *true*

- `buyBoxIsPreorder`:
  If the product’s Buy Box is a preorder. Example: *true*

- `buyBoxIsBackorder`:
  If the product’s Buy Box is backordered. Example: *true*

- `buyBoxIsPrimeExclusive`:
  If the product’s Buy Box is prime exclusive. Example: *true*

- `current` [_PriceType] [_lte, _gte]:
  Filter for the current price or value. The price is an integer of the respective Amazon locale’s smallest currency unit (e.g., euro cents or yen).

- `delta` [1, 7, 30, 90] [_PriceType] [_lte, _gte]:
  Filter for the absolute difference between the current value and the 1, 7, 30 or 90-day average value. The price is an integer of the respective Amazon locale’s smallest currency unit (e.g., euro cents or yen). A negative value filters for prices/values that have increased, and a positive value filters for decreased ones. A **0** filters products with no change.

- `deltaPercent` [1, 7, 30, 90] [_PriceType] [_lte, _gte]:
  Filter for the relative difference between the current value and the 1, 7, 30 or 90-day average value. In percentage between 0 and 100%. A positive value filters for prices/values that have decreased, and a negative value filters for increased ones. A **0** filters products with no change.

- `deltaLast` [_PriceType] [_lte, _gte]:
  Filter for the difference between the current value and the previous value. The price is an integer of the respective Amazon locale’s smallest currency unit (e.g., euro cents or yen). A positive value filters for prices/values that have decreased, and a negative value filters for increased ones. A **0** filters products with no change.

- `avg` [7, 30, 90, 180, 365] [_PriceType] [_lte, _gte]:
  Filter for the average price or value of the respective last x days. The price is an integer of the respective Amazon locale’s smallest currency unit (e.g., euro cents or yen).

- `backInStock` [_PriceType]:
  Whether or not the price/value was out of stock in the last 60 days and now has an offer again.

- `isLowest` [_PriceType]:
  Whether or not the current price/value is the lowest ever.

- `isLowest90` [_PriceType]:
  Whether or not the current price/value is the lowest in the last 90 days.

**Keepa Time minutes:**
Time format used for all timestamps. To convert to an uncompressed Unix epoch time:

- **For milliseconds**: `(keepaTime + 21564000) * 60000`
- **For seconds**: `(keepaTime + 21564000) * 60`

**Example Query:**

```javascript
{
  "rootCategory": 3167641,
  "current_AMAZON_lte": 5000,
  "current_AMAZON_gte": 1000,
  "perPage": 100,
  "page": 0
}
```

A query can also be build by using our [Product Finder](https://keepa.com/#!finder) interface. The current query can be reviewed by clicking on “Show API query” above the result table.

------

**Response:**

```javascript
{
    "asinList" : String array,
    "searchInsights" : Search Insights Object,
    "totalResults" : Integer,
}
```

- asinList
  Ordered array with the result ASINs
- searchInsights
  Aggregated metrics calculated over matched products: [Search Insights Object](https://discuss.keepa.com/t/search-insights-object/18199). Requires the *&stats=1* parameter.
- totalResults
  Estimated count of all matched products.



# Request Best Sellers

**Token Cost:** 50

Retrieve an ASIN list of the most popular products based on sales in a specific category or product group.

**Note:** We cannot always correctly identify the sales rank reference category, so some products may be misplaced.

- **Root Category Lists**: (e.g., “Home & Kitchen”) contain up to **500,000** ASINs. For a list of all available root categories, use the [Category Lookup](https://discuss.keepa.com/t/category-lookup/113) with the `categoryId` **0**.
- **Sub-category Lists**: (e.g., “Home Entertainment Furniture”) contain up to **10,000** ASINs. By default, sub-category lists are created based on the product’s primary sales rank and do not reflect the actual ordering on Amazon. See the `sublist` parameter.
- **Product Group Lists**: (e.g., “Beauty”) contain up to **100,000** ASINs.
- **Updates**: Lists are usually updated hourly.
- **Ordering**: Lists are ordered starting with the best-selling product. Since lists are cached for up to one hour, the ordering may be outdated.
- **Exclusions**: Products without an accessible sales rank are not included.

------

## Query

```php-template
/bestsellers?key=<yourAccessKey>&domain=<domainId>&category=<categoryId>&range=<range>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access. The Brazil locale is not applicable for this request.

  **Valid values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- `<categoryId>`: The category node ID for which you want the best sellers list. You can find category node IDs via the [Category Search](https://discuss.keepa.com/t/category-searches/114), the [Deals](https://keepa.com/#!deals) page (select the category and click on “Show API query”), or directly on Amazon.

  Alternatively, you can provide a product group (e.g., “Beauty”), which can be found in the `productGroup` field of the product object.

- `<range>`: Optionally specify to retrieve a best seller list based on a sales rank average instead of the current sales rank.

  **Valid values:**

  - **0**: Use current rank
  - **30**: 30-day average
  - **90**: 90-day average
  - **180**: 180-day average

------

## Optional Parameters

- `month` & `year`: Request a historical best seller list for a specific month.
- `variations`: Include all variations for items with multiple variations.
- `sublist`: Create the best seller list based on the sub-category sales rank.

------

### `month` & `year`

Request a historical best seller list for a specific month, based on the average rank during that month. We maintain lists for the last **36 months**. Requests for the current calendar month or any month beyond 36 months ago are not permitted.

**Note:** If using these parameters, both `month` and `year` must be specified. The `range` parameter must not be used concurrently.

- Valid values:
  - `month`: Integer between **1** and **12**, representing January to December.
  - `year`: 4-digit year (e.g., **2024**).

**Examples:**

- `month=6&year=2024` (June 2024)
- `month=11&year=2023` (November 2023)

------

### `variations`

Restrict list entries to a single variation for items with multiple variations. The variation returned will be the one with the highest monthly units sold (if that data point is available).

- Valid values:
  - **0**: Do not include variations (default)
  - **1**: Include all variations

### `variations`

Controls whether items with multiple variations are returned as a single representative or as all variations.

- By default, we return one variation per parent. If the variations share the same sales rank, the representative is the variation with the highest monthly units sold. If monthly sold data is missing or tied, the representative falls back to randomly picked one.

**Valid values**

- `0` — **Collapse to one variation per parent** (default)
  Selection rule: Sales Rank, then highest monthly sold.
- `1` — **Return all variations**

------

------

### `sublist`

By default, the best seller list for sub-categories is created based on the product’s primary sales rank, if available. To request a best seller list based on the sub-category sales rank (classification rank), use the `sublist` parameter with the value **1**. The `range`, `month`, and `year` parameters must not be used concurrently.

**Notes:**

- Not all products have a primary sales rank or a sub-category sales rank.
- Not all sub-category levels have sales ranks.
- **Valid values:**
  - **0**: List is based on primary rank (default)
  - **1**: List is based on sub-category rank

------

## Response

The response contains a `bestSellersList` field with a [Best Sellers object](https://discuss.keepa.com/t/best-sellers-object/1299). If no list for the specified category and locale could be found, the response will be empty (no token will be consumed in this case).



# Graph Image API

**Token Cost:** 1 per image

Retrieve a price history graph image of a product in PNG format:



[![Graph Image Example](https://discuss.keepa.com/uploads/default/original/2X/2/2362dd6725f6beb5dff773c4b26cf5c83ec17253.png)Graph Image Example500×200 30.4 KB](https://discuss.keepa.com/uploads/default/original/2X/2/2362dd6725f6beb5dff773c4b26cf5c83ec17253.png)



*Graph images are cached for 90 minutes on a per-user basis. The cache invalidates if any parameter changes. Submitting the exact same request within this time frame will not consume any tokens.*

**Important:** Make sure you do **not** embed the images directly, as this will make your API key publicly accessible and open to misuse. Always put the Graph Image requests behind a proxy to secure your API key.

This API call returns PNG images as a response and does not provide your token status information. You can use the free [token request](https://discuss.keepa.com/t/retrieve-token-status/1305) to retrieve your token status.

------

## Basic Request

```php-template
api.keepa.com/graphimage?key=<yourAccessKey>&domain=<domainId>&asin=<ASIN>
```

### Parameters

- `<yourAccessKey>`: Your private API key.

- `<domainId>`: Integer value for the Amazon locale you want to access.

  **Valid values:**

  | Domain ID | Locale |
  | :-------- | :----- |
  | **1**     | com    |
  | **2**     | co.uk  |
  | **3**     | de     |
  | **4**     | fr     |
  | **5**     | co.jp  |
  | **6**     | ca     |
  | **8**     | it     |
  | **9**     | es     |
  | **10**    | in     |
  | **11**    | com.mx |

- `<ASIN>`: The ASIN of the product.

------

## Optional Parameters

### Graph Data Parameters

- **`amazon`**: Amazon price graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `1`
  - **Example:** `&amazon=1`
- **`new`**: New price graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `1`
  - **Example:** `&new=1`
- **`used`**: Used price graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&used=0`
- **`salesrank`**: Sales Rank graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&salesrank=0`
- **`bb`**: Buy Box graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&bb=1`
- **`bbu`**: Used Buy Box graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&bbu=1`
- **`fba`**: New, 3rd party FBA graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&fba=0`
- **`fbm`**: New, FBM graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&fbm=0`
- **`ld`**: Lightning Deals graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&ld=1`
- **`wd`**: Warehouse Deals graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&wd=1`
- **`pe`**: New, Prime exclusive graph.
  - **Valid values:** `1` (draw), `0` (do not draw)
  - **Default value:** `0`
  - **Example:** `&pe=1`

### Display Parameters

- **`range`**: The range of the chart in days.
  - **Suggested values:** `1`, `2`, `7`, `31`, `90`, `365`
  - **Default value:** `90`
  - **Example:** `&range=90`
- **`yzoom`**: Enable Close-up View (y-axis zoom).
  - **Valid values:** `1` (zoom), `0` (no zoom)
  - **Default value:** `1`
  - **Example:** `&yzoom=0`
- **`width`**: Width of the chart image in pixels.
  - **Valid range:** `300` to `1000`
  - **Default value:** `500`
  - **Example:** `&width=500`
- **`height`**: Height of the chart image in pixels.
  - **Valid range:** `150` to `1000`
  - **Default value:** `200`
  - **Example:** `&height=200`
- **`title`**: Include the product title.
  - **Valid values:** `1` (show), `0` (hide)
  - **Default value:** `1`
  - **Example:** `&title=0`

------

## Customizing the Color Scheme

The following parameters allow you to customize the colors of various chart elements. All color parameters are hexadecimal color codes (e.g., `ff0000`). These parameters are optional.

- **`cBackground`**: Chart background color.
  - **Example:** `&cBackground=ffffff`
- **`cFont`**: Font color.
  - **Example:** `&cFont=444444`
- **`cAmazon`**: Color of the Amazon graph.
  - **Example:** `&cAmazon=FFA500`
- **`cNew`**: Color of the New graph.
  - **Example:** `&cNew=8888dd`
- **`cUsed`**: Color of the Used graph.
  - **Example:** `&cUsed=444444`
- **`cSales`**: Color of the Sales Rank graph.
  - **Example:** `&cSales=3a883a`
- **`cFBA`**: Color of the FBA graph.
  - **Example:** `&cFBA=ff5722`
- **`cFBM`**: Color of the FBM graph.
  - **Example:** `&cFBM=039BE5`
- **`cBB`**: Color of the Buy Box graph.
  - **Example:** `&cBB=ff00b4`
- **`cBBU`**: Color of the Used Buy Box graph.
  - **Example:** `&cBBU=da66ff`
- **`cLD`**: Color of the Lightning Deals graph.
  - **Example:** `&cLD=ff0000`
- **`cWD`**: Color of the Warehouse Deals graph.
  - **Example:** `&cWD=9c27b0`
- **`cPE`**: Color of the New, Prime exclusive graph.
  - **Example:** `&cWD=9c27b0`
