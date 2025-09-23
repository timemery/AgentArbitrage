[Skip to main content](https://keepaapi.readthedocs.io/en/latest/api_methods.html#main-content)
[![Logo image][image1]](https://keepaapi.readthedocs.io/en/latest/api_methods.html#main-content)

* [Queries](https://keepaapi.readthedocs.io/en/latest/product_query.html)
* [keepa.Api Methods](https://keepaapi.readthedocs.io/en/latest/api_methods.html#)
* [GitHub](https://github.com/akaszynski/keepa)

# keepa.Api Methods

***class*** **keepa.Keepa(*accesskey*, *timeout=10*, *logging\_level='DEBUG'*)**

Support a synchronous Python interface to keepa server.

Initializes API with access key. Access key can be obtained by signing up for a reoccurring or one time plan at: [https://keepa.com/\#\!api](https://keepa.com/#!api)

**Parameters:**

* accesskey (*str*) – 64 character access key string.
* timeout (*float, optional*) – Default timeout when issuing any request. This is not a time limit on the entire response download; rather, an exception is raised if the server has not issued a response for timeout seconds. Setting this to 0 disables the timeout, but will cause any request to hang indefiantly should keepa.com be down
* logging\_level (*string, optional*) – Logging level to use. Default is ‘DEBUG’. Other options are ‘INFO’, ‘WARNING’, ‘ERROR’, and ‘CRITICAL’.

**Examples**

Create the api object.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**

Request data from two ASINs.

\>\>\> products **\=** api**.**query**(\[**'0439064872'**,** '1426208081'**\])**

Print item details.

\>\>\> print**(**'Item 1'**)**
\>\>\> print**(**'\\t ASIN: {:s}'**.**format**(**products**\[0\]\[**'asin'**\]))**
\>\>\> print**(**'\\t Title: {:s}'**.**format**(**products**\[0\]\[**'title'**\]))**
*Item 1*
    *ASIN: 0439064872*
    *Title: Harry Potter and the Chamber of Secrets (2)*

Print item price.

\>\>\> usedprice **\=** products**\[0\]\[**'data'**\]\[**'USED'**\]**
\>\>\> usedtimes **\=** products**\[0\]\[**'data'**\]\[**'USED\_time'**\]**
\>\>\> print**(**'\\t Used price: ${:.2f}'**.**format**(**usedprice**\[\-1\]))**
\>\>\> print**(**'\\t as of: {:s}'**.**format**(**str**(**usedtimes**\[\-1\])))**
    *Used price: $0.52*
    *as of: 2023-01-03 04:46:00*

**best\_sellers\_query(*category*, *rank\_avg\_range=0*, *domain='US'*, *wait=True*)**

Retrieve an ASIN list of the most popular products.

This is based on sales in a specific category or product group. See “search\_for\_categories” for information on how to get a category.

Root category lists (e.g. “Home & Kitchen”) or product group lists contain up to 100,000 ASINs.

Sub-category lists (e.g. “Home Entertainment Furniture”) contain up to 3,000 ASINs. As we only have access to the product’s primary sales rank and not the ones of all categories it is listed in, the sub-category lists are created by us based on the product’s primary sales rank and do not reflect the actual ordering on Amazon.

Lists are ordered, starting with the best selling product.

Lists are updated daily. If a product does not have an accessible sales rank it will not be included in the lists. This in particular affects many products in the Clothing and Sports & Outdoors categories.

We can not correctly identify the sales rank reference category in all cases, so some products may be misplaced.

**Parameters:**

* category (*str*) – The category node id of the category you want to request the best sellers list for. You can find category node ids via the category search “search\_for\_categories”.
* domain (*str*) – Amazon locale you want to access. Must be one of the following RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX Default US.
* wait (*bool, optional*) – Wait available token before doing effective query. Defaults to `True`.

**Returns:**

best\_sellers – List of best seller ASINs

**Return type:**

list

**Examples**

Query for the best sellers among the `"movies"` category.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> categories **\=** api**.**search\_for\_categories**(**"movies"**)**
\>\>\> category **\=** list**(**categories**.**items**())\[0\]\[0\]**
\>\>\> asins **\=** api**.**best\_sellers\_query**(**category**)**
\>\>\> asins
*\['B0BF3P5XZS',*
 *'B08JQN5VDT',*
 *'B09SP8JPPK',*
 *'0999296345',*
 *'B07HPG684T',*
 *'1984825577',*
*...*

Query for the best sellers among the `"movies"` category using the asynchronous keepa interface.

\>\>\> **import** asyncio
\>\>\> **import** keepa
\>\>\> **async** **def** main**():**
...    key **\=** '\<REAL\_KEEPA\_KEY\>'
...    api **\=** **await** keepa**.**AsyncKeepa**().**create**(**key**)**
...    categories **\=** **await** api**.**search\_for\_categories**(**"movies"**)**
...    category **\=** list**(**categories**.**items**())\[0\]\[0\]**
...    **return** **await** api**.**best\_sellers\_query**(**category**)**
\>\>\> asins **\=** asyncio**.**run**(**main**())**
\>\>\> asins
*\['B0BF3P5XZS',*
 *'B08JQN5VDT',*
 *'B09SP8JPPK',*
 *'0999296345',*
 *'B07HPG684T',*
 *'1984825577',*
*...*

**category\_lookup(*category\_id*, *domain='US'*, *include\_parents=False*, *wait=True*)**

Return root categories given a categoryId.

**Parameters:**

* category\_id (*int*) – ID for specific category or 0 to return a list of root categories.
* domain (*str, default: "US"*) – Amazon locale you want to access. Must be one of the following RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX Default US
* include\_parents (*bool, default: False*) – Include parents.
* wait (*bool, default: True*) – Wait available token before doing effective query.

**Returns:**

Output format is the same as search\_for\_categories.

**Return type:**

list

**Examples**

Use 0 to return all root categories.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> categories **\=** api**.**category\_lookup**(0)**

Print all root categories

\>\>\> **for** cat\_id **in** categories**:**
\>\>\>    print**(**cat\_id**,** categories**\[**cat\_id**\]\[**'name'**\])**
*133140011 Kindle Store*
*9013971011 Video Shorts*
*2350149011 Apps & Games*
*165796011 Baby Products*
*163856011 Digital Music*
*13727921011 Alexa Skills*
*...*

**deals(*deal\_parms*, *domain='US'*, *wait=True*) → dict**

Query the Keepa API for product deals.

You can find products that recently changed and match your search criteria. A single request will return a maximum of 150 deals. Try out the deals page to first get accustomed to the options: [https://keepa.com/\#\!deals](https://keepa.com/#!deals)

For more details please visit: [https://keepa.com/\#\!discuss/t/browsing-deals/338](https://keepa.com/#!discuss/t/browsing-deals/338)

**Parameters:**

* deal\_parms (*dict*) –
  Dictionary containing one or more of the following keys:
  * `"page"`: int
  * `"domainId"`: int
  * `"excludeCategories"`: list
  * `"includeCategories"`: list
  * `"priceTypes"`: list
  * `"deltaRange"`: list
  * `"deltaPercentRange"`: list
  * `"deltaLastRange"`: list
  * `"salesRankRange"`: list
  * `"currentRange"`: list
  * `"minRating"`: int
  * `"isLowest"`: bool
  * `"isLowestOffer"`: bool
  * `"isOutOfStock"`: bool
  * `"titleSearch"`: String
  * `"isRangeEnabled"`: bool
  * `"isFilterEnabled"`: bool
  * `"hasReviews"`: bool
  * `"filterErotic"`: bool
  * `"sortType"`: int
  * `"dateRange"`: int
* domain (*str, optional*) – One of the following Amazon domains: RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX Defaults to US.
* wait (*bool, optional*) – Wait available token before doing effective query, Defaults to `True`.

**Returns:**

Dictionary containing the deals including the following keys:

* `'dr'` \- Ordered array of all deal objects matching your query.
* `'categoryIds'` \- Contains all root categoryIds of the matched deal products.
* `'categoryNames'` \- Contains all root category names of the matched deal products.
* `'categoryCount'` \- Contains how many deal products in the respective root category are found.

**Return type:**

dict

**Examples**

Return deals from category 16310101 using the synchronous `keepa.Keepa` class

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> deal\_parms **\=** **{**"page"**:** **0,**
...              "domainId"**:** **1,**
...              "excludeCategories"**:** **\[1064954,** **11091801\],**
...              "includeCategories"**:** **\[16310101\]}**
\>\>\> deals **\=** api**.**deals**(**deal\_parms**)**

Get the title of the first deal.

\>\>\> deals**\[**'dr'**\]\[0\]\[**'title'**\]**
*'Orange Cream Rooibos, Tea Bags \- Vanilla, Orange | Caffeine-Free,*
*Antioxidant-rich, Hot & Iced | The Spice Hut, First Sip Of Tea'*

Conduct the same query with the asynchronous `keepa.AsyncKeepa` class.

\>\>\> **import** asyncio
\>\>\> **import** keepa
\>\>\> deal\_parms **\=** **{**"page"**:** **0,**
...              "domainId"**:** **1,**
...              "excludeCategories"**:** **\[1064954,** **11091801\],**
...              "includeCategories"**:** **\[16310101\]}**
\>\>\> **async** **def** main**():**
...    key **\=** '\<REAL\_KEEPA\_KEY\>'
...    api **\=** **await** keepa**.**AsyncKeepa**().**create**(**key**)**
...    categories **\=** **await** api**.**search\_for\_categories**(**"movies"**)**
...    **return** **await** api**.**deals**(**deal\_parms**)**
\>\>\> asins **\=** asyncio**.**run**(**main**())**
\>\>\> asins
*\['B0BF3P5XZS',*
 *'B08JQN5VDT',*
 *'B09SP8JPPK',*
 *'0999296345',*
 *'B07HPG684T',*
 *'1984825577',*
*...*

**product\_finder(*product\_parms*, *domain='US'*, *wait=True*) → list**

Query the keepa product database to find products matching criteria.

Almost all product fields can be searched for and sort.

**Parameters:**

* product\_parms (*dict*) –
  Dictionary containing one or more of the following keys:
  * `'author': str`
  * `'availabilityAmazon': int`
  * `'avg180_AMAZON_lte': int`
  * `'avg180_AMAZON_gte': int`
  * `'avg180_BUY_BOX_SHIPPING_lte': int`
  * `'avg180_BUY_BOX_SHIPPING_gte': int`
  * `'avg180_COLLECTIBLE_lte': int`
  * `'avg180_COLLECTIBLE_gte': int`
  * `'avg180_COUNT_COLLECTIBLE_lte': int`
  * `'avg180_COUNT_COLLECTIBLE_gte': int`
  * `'avg180_COUNT_NEW_lte': int`
  * `'avg180_COUNT_NEW_gte': int`
  * `'avg180_COUNT_REFURBISHED_lte': int`
  * `'avg180_COUNT_REFURBISHED_gte': int`
  * `'avg180_COUNT_REVIEWS_lte': int`
  * `'avg180_COUNT_REVIEWS_gte': int`
  * `'avg180_COUNT_USED_lte': int`
  * `'avg180_COUNT_USED_gte': int`
  * `'avg180_EBAY_NEW_SHIPPING_lte': int`
  * `'avg180_EBAY_NEW_SHIPPING_gte': int`
  * `'avg180_EBAY_USED_SHIPPING_lte': int`
  * `'avg180_EBAY_USED_SHIPPING_gte': int`
  * `'avg180_LIGHTNING_DEAL_lte': int`
  * `'avg180_LIGHTNING_DEAL_gte': int`
  * `'avg180_LISTPRICE_lte': int`
  * `'avg180_LISTPRICE_gte': int`
  * `'avg180_NEW_lte': int`
  * `'avg180_NEW_gte': int`
  * `'avg180_NEW_FBA_lte': int`
  * `'avg180_NEW_FBA_gte': int`
  * `'avg180_NEW_FBM_SHIPPING_lte': int`
  * `'avg180_NEW_FBM_SHIPPING_gte': int`
  * `'avg180_RATING_lte': int`
  * `'avg180_RATING_gte': int`
  * `'avg180_REFURBISHED_lte': int`
  * `'avg180_REFURBISHED_gte': int`
  * `'avg180_REFURBISHED_SHIPPING_lte': int`
  * `'avg180_REFURBISHED_SHIPPING_gte': int`
  * `'avg180_RENT_lte': int`
  * `'avg180_RENT_gte': int`
  * `'avg180_SALES_lte': int`
  * `'avg180_SALES_gte': int`
  * `'avg180_TRADE_IN_lte': int`
  * `'avg180_TRADE_IN_gte': int`
  * `'avg180_USED_lte': int`
  * `'avg180_USED_gte': int`
  * `'avg180_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'avg180_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'avg180_USED_GOOD_SHIPPING_lte': int`
  * `'avg180_USED_GOOD_SHIPPING_gte': int`
  * `'avg180_USED_NEW_SHIPPING_lte': int`
  * `'avg180_USED_NEW_SHIPPING_gte': int`
  * `'avg180_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'avg180_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'avg180_WAREHOUSE_lte': int`
  * `'avg180_WAREHOUSE_gte': int`
  * `'avg1_AMAZON_lte': int`
  * `'avg1_AMAZON_gte': int`
  * `'avg1_BUY_BOX_SHIPPING_lte': int`
  * `'avg1_BUY_BOX_SHIPPING_gte': int`
  * `'avg1_COLLECTIBLE_lte': int`
  * `'avg1_COLLECTIBLE_gte': int`
  * `'avg1_COUNT_COLLECTIBLE_lte': int`
  * `'avg1_COUNT_COLLECTIBLE_gte': int`
  * `'avg1_COUNT_NEW_lte': int`
  * `'avg1_COUNT_NEW_gte': int`
  * `'avg1_COUNT_REFURBISHED_lte': int`
  * `'avg1_COUNT_REFURBISHED_gte': int`
  * `'avg1_COUNT_REVIEWS_lte': int`
  * `'avg1_COUNT_REVIEWS_gte': int`
  * `'avg1_COUNT_USED_lte': int`
  * `'avg1_COUNT_USED_gte': int`
  * `'avg1_EBAY_NEW_SHIPPING_lte': int`
  * `'avg1_EBAY_NEW_SHIPPING_gte': int`
  * `'avg1_EBAY_USED_SHIPPING_lte': int`
  * `'avg1_EBAY_USED_SHIPPING_gte': int`
  * `'avg1_LIGHTNING_DEAL_lte': int`
  * `'avg1_LIGHTNING_DEAL_gte': int`
  * `'avg1_LISTPRICE_lte': int`
  * `'avg1_LISTPRICE_gte': int`
  * `'avg1_NEW_lte': int`
  * `'avg1_NEW_gte': int`
  * `'avg1_NEW_FBA_lte': int`
  * `'avg1_NEW_FBA_gte': int`
  * `'avg1_NEW_FBM_SHIPPING_lte': int`
  * `'avg1_NEW_FBM_SHIPPING_gte': int`
  * `'avg1_RATING_lte': int`
  * `'avg1_RATING_gte': int`
  * `'avg1_REFURBISHED_lte': int`
  * `'avg1_REFURBISHED_gte': int`
  * `'avg1_REFURBISHED_SHIPPING_lte': int`
  * `'avg1_REFURBISHED_SHIPPING_gte': int`
  * `'avg1_RENT_lte': int`
  * `'avg1_RENT_gte': int`
  * `'avg1_SALES_lte': int`
  * `'avg1_SALES_lte': int`
  * `'avg1_SALES_gte': int`
  * `'avg1_TRADE_IN_lte': int`
  * `'avg1_TRADE_IN_gte': int`
  * `'avg1_USED_lte': int`
  * `'avg1_USED_gte': int`
  * `'avg1_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'avg1_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'avg1_USED_GOOD_SHIPPING_lte': int`
  * `'avg1_USED_GOOD_SHIPPING_gte': int`
  * `'avg1_USED_NEW_SHIPPING_lte': int`
  * `'avg1_USED_NEW_SHIPPING_gte': int`
  * `'avg1_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'avg1_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'avg1_WAREHOUSE_lte': int`
  * `'avg1_WAREHOUSE_gte': int`
  * `'avg30_AMAZON_lte': int`
  * `'avg30_AMAZON_gte': int`
  * `'avg30_BUY_BOX_SHIPPING_lte': int`
  * `'avg30_BUY_BOX_SHIPPING_gte': int`
  * `'avg30_COLLECTIBLE_lte': int`
  * `'avg30_COLLECTIBLE_gte': int`
  * `'avg30_COUNT_COLLECTIBLE_lte': int`
  * `'avg30_COUNT_COLLECTIBLE_gte': int`
  * `'avg30_COUNT_NEW_lte': int`
  * `'avg30_COUNT_NEW_gte': int`
  * `'avg30_COUNT_REFURBISHED_lte': int`
  * `'avg30_COUNT_REFURBISHED_gte': int`
  * `'avg30_COUNT_REVIEWS_lte': int`
  * `'avg30_COUNT_REVIEWS_gte': int`
  * `'avg30_COUNT_USED_lte': int`
  * `'avg30_COUNT_USED_gte': int`
  * `'avg30_EBAY_NEW_SHIPPING_lte': int`
  * `'avg30_EBAY_NEW_SHIPPING_gte': int`
  * `'avg30_EBAY_USED_SHIPPING_lte': int`
  * `'avg30_EBAY_USED_SHIPPING_gte': int`
  * `'avg30_LIGHTNING_DEAL_lte': int`
  * `'avg30_LIGHTNING_DEAL_gte': int`
  * `'avg30_LISTPRICE_lte': int`
  * `'avg30_LISTPRICE_gte': int`
  * `'avg30_NEW_lte': int`
  * `'avg30_NEW_gte': int`
  * `'avg30_NEW_FBA_lte': int`
  * `'avg30_NEW_FBA_gte': int`
  * `'avg30_NEW_FBM_SHIPPING_lte': int`
  * `'avg30_NEW_FBM_SHIPPING_gte': int`
  * `'avg30_RATING_lte': int`
  * `'avg30_RATING_gte': int`
  * `'avg30_REFURBISHED_lte': int`
  * `'avg30_REFURBISHED_gte': int`
  * `'avg30_REFURBISHED_SHIPPING_lte': int`
  * `'avg30_REFURBISHED_SHIPPING_gte': int`
  * `'avg30_RENT_lte': int`
  * `'avg30_RENT_gte': int`
  * `'avg30_SALES_lte': int`
  * `'avg30_SALES_gte': int`
  * `'avg30_TRADE_IN_lte': int`
  * `'avg30_TRADE_IN_gte': int`
  * `'avg30_USED_lte': int`
  * `'avg30_USED_gte': int`
  * `'avg30_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'avg30_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'avg30_USED_GOOD_SHIPPING_lte': int`
  * `'avg30_USED_GOOD_SHIPPING_gte': int`
  * `'avg30_USED_NEW_SHIPPING_lte': int`
  * `'avg30_USED_NEW_SHIPPING_gte': int`
  * `'avg30_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'avg30_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'avg30_WAREHOUSE_lte': int`
  * `'avg30_WAREHOUSE_gte': int`
  * `'avg7_AMAZON_lte': int`
  * `'avg7_AMAZON_gte': int`
  * `'avg7_BUY_BOX_SHIPPING_lte': int`
  * `'avg7_BUY_BOX_SHIPPING_gte': int`
  * `'avg7_COLLECTIBLE_lte': int`
  * `'avg7_COLLECTIBLE_gte': int`
  * `'avg7_COUNT_COLLECTIBLE_lte': int`
  * `'avg7_COUNT_COLLECTIBLE_gte': int`
  * `'avg7_COUNT_NEW_lte': int`
  * `'avg7_COUNT_NEW_gte': int`
  * `'avg7_COUNT_REFURBISHED_lte': int`
  * `'avg7_COUNT_REFURBISHED_gte': int`
  * `'avg7_COUNT_REVIEWS_lte': int`
  * `'avg7_COUNT_REVIEWS_gte': int`
  * `'avg7_COUNT_USED_lte': int`
  * `'avg7_COUNT_USED_gte': int`
  * `'avg7_EBAY_NEW_SHIPPING_lte': int`
  * `'avg7_EBAY_NEW_SHIPPING_gte': int`
  * `'avg7_EBAY_USED_SHIPPING_lte': int`
  * `'avg7_EBAY_USED_SHIPPING_gte': int`
  * `'avg7_LIGHTNING_DEAL_lte': int`
  * `'avg7_LIGHTNING_DEAL_gte': int`
  * `'avg7_LISTPRICE_lte': int`
  * `'avg7_LISTPRICE_gte': int`
  * `'avg7_NEW_lte': int`
  * `'avg7_NEW_gte': int`
  * `'avg7_NEW_FBA_lte': int`
  * `'avg7_NEW_FBA_gte': int`
  * `'avg7_NEW_FBM_SHIPPING_lte': int`
  * `'avg7_NEW_FBM_SHIPPING_gte': int`
  * `'avg7_RATING_lte': int`
  * `'avg7_RATING_gte': int`
  * `'avg7_REFURBISHED_lte': int`
  * `'avg7_REFURBISHED_gte': int`
  * `'avg7_REFURBISHED_SHIPPING_lte': int`
  * `'avg7_REFURBISHED_SHIPPING_gte': int`
  * `'avg7_RENT_lte': int`
  * `'avg7_RENT_gte': int`
  * `'avg7_SALES_lte': int`
  * `'avg7_SALES_gte': int`
  * `'avg7_TRADE_IN_lte': int`
  * `'avg7_TRADE_IN_gte': int`
  * `'avg7_USED_lte': int`
  * `'avg7_USED_gte': int`
  * `'avg7_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'avg7_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'avg7_USED_GOOD_SHIPPING_lte': int`
  * `'avg7_USED_GOOD_SHIPPING_gte': int`
  * `'avg7_USED_NEW_SHIPPING_lte': int`
  * `'avg7_USED_NEW_SHIPPING_gte': int`
  * `'avg7_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'avg7_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'avg7_WAREHOUSE_lte': int`
  * `'avg7_WAREHOUSE_gte': int`
  * `'avg90_AMAZON_lte': int`
  * `'avg90_AMAZON_gte': int`
  * `'avg90_BUY_BOX_SHIPPING_lte': int`
  * `'avg90_BUY_BOX_SHIPPING_gte': int`
  * `'avg90_COLLECTIBLE_lte': int`
  * `'avg90_COLLECTIBLE_gte': int`
  * `'avg90_COUNT_COLLECTIBLE_lte': int`
  * `'avg90_COUNT_COLLECTIBLE_gte': int`
  * `'avg90_COUNT_NEW_lte': int`
  * `'avg90_COUNT_NEW_gte': int`
  * `'avg90_COUNT_REFURBISHED_lte': int`
  * `'avg90_COUNT_REFURBISHED_gte': int`
  * `'avg90_COUNT_REVIEWS_lte': int`
  * `'avg90_COUNT_REVIEWS_gte': int`
  * `'avg90_COUNT_USED_lte': int`
  * `'avg90_COUNT_USED_gte': int`
  * `'avg90_EBAY_NEW_SHIPPING_lte': int`
  * `'avg90_EBAY_NEW_SHIPPING_gte': int`
  * `'avg90_EBAY_USED_SHIPPING_lte': int`
  * `'avg90_EBAY_USED_SHIPPING_gte': int`
  * `'avg90_LIGHTNING_DEAL_lte': int`
  * `'avg90_LIGHTNING_DEAL_gte': int`
  * `'avg90_LISTPRICE_lte': int`
  * `'avg90_LISTPRICE_gte': int`
  * `'avg90_NEW_lte': int`
  * `'avg90_NEW_gte': int`
  * `'avg90_NEW_FBA_lte': int`
  * `'avg90_NEW_FBA_gte': int`
  * `'avg90_NEW_FBM_SHIPPING_lte': int`
  * `'avg90_NEW_FBM_SHIPPING_gte': int`
  * `'avg90_RATING_lte': int`
  * `'avg90_RATING_gte': int`
  * `'avg90_REFURBISHED_lte': int`
  * `'avg90_REFURBISHED_gte': int`
  * `'avg90_REFURBISHED_SHIPPING_lte': int`
  * `'avg90_REFURBISHED_SHIPPING_gte': int`
  * `'avg90_RENT_lte': int`
  * `'avg90_RENT_gte': int`
  * `'avg90_SALES_lte': int`
  * `'avg90_SALES_gte': int`
  * `'avg90_TRADE_IN_lte': int`
  * `'avg90_TRADE_IN_gte': int`
  * `'avg90_USED_lte': int`
  * `'avg90_USED_gte': int`
  * `'avg90_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'avg90_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'avg90_USED_GOOD_SHIPPING_lte': int`
  * `'avg90_USED_GOOD_SHIPPING_gte': int`
  * `'avg90_USED_NEW_SHIPPING_lte': int`
  * `'avg90_USED_NEW_SHIPPING_gte': int`
  * `'avg90_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'avg90_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'avg90_WAREHOUSE_lte': int`
  * `'avg90_WAREHOUSE_gte': int`
  * `'backInStock_AMAZON': bool`
  * `'backInStock_BUY_BOX_SHIPPING': bool`
  * `'backInStock_COLLECTIBLE': bool`
  * `'backInStock_COUNT_COLLECTIBLE': bool`
  * `'backInStock_COUNT_NEW': bool`
  * `'backInStock_COUNT_REFURBISHED': bool`
  * `'backInStock_COUNT_REVIEWS': bool`
  * `'backInStock_COUNT_USED': bool`
  * `'backInStock_EBAY_NEW_SHIPPING': bool`
  * `'backInStock_EBAY_USED_SHIPPING': bool`
  * `'backInStock_LIGHTNING_DEAL': bool`
  * `'backInStock_LISTPRICE': bool`
  * `'backInStock_NEW': bool`
  * `'backInStock_NEW_FBA': bool`
  * `'backInStock_NEW_FBM_SHIPPING': bool`
  * `'backInStock_RATING': bool`
  * `'backInStock_REFURBISHED': bool`
  * `'backInStock_REFURBISHED_SHIPPING': bool`
  * `'backInStock_RENT': bool`
  * `'backInStock_SALES': bool`
  * `'backInStock_TRADE_IN': bool`
  * `'backInStock_USED': bool`
  * `'backInStock_USED_ACCEPTABLE_SHIPPING': bool`
  * `'backInStock_USED_GOOD_SHIPPING': bool`
  * `'backInStock_USED_NEW_SHIPPING': bool`
  * `'backInStock_USED_VERY_GOOD_SHIPPING': bool`
  * `'backInStock_WAREHOUSE': bool`
  * `'binding': str`
  * `'brand': str`
  * `'buyBoxSellerId': str`
  * `'color': str`
  * `'couponOneTimeAbsolute_lte': int`
  * `'couponOneTimeAbsolute_gte': int`
  * `'couponOneTimePercent_lte': int`
  * `'couponOneTimePercent_gte': int`
  * `'couponSNSAbsolute_lte': int`
  * `'couponSNSAbsolute_gte': int`
  * `'couponSNSPercent_lte': int`
  * `'couponSNSPercent_gte': int`
  * `'current_AMAZON_lte': int`
  * `'current_AMAZON_gte': int`
  * `'current_BUY_BOX_SHIPPING_lte': int`
  * `'current_BUY_BOX_SHIPPING_gte': int`
  * `'current_COLLECTIBLE_lte': int`
  * `'current_COLLECTIBLE_gte': int`
  * `'current_COUNT_COLLECTIBLE_lte': int`
  * `'current_COUNT_COLLECTIBLE_gte': int`
  * `'current_COUNT_NEW_lte': int`
  * `'current_COUNT_NEW_gte': int`
  * `'current_COUNT_REFURBISHED_lte': int`
  * `'current_COUNT_REFURBISHED_gte': int`
  * `'current_COUNT_REVIEWS_lte': int`
  * `'current_COUNT_REVIEWS_gte': int`
  * `'current_COUNT_USED_lte': int`
  * `'current_COUNT_USED_gte': int`
  * `'current_EBAY_NEW_SHIPPING_lte': int`
  * `'current_EBAY_NEW_SHIPPING_gte': int`
  * `'current_EBAY_USED_SHIPPING_lte': int`
  * `'current_EBAY_USED_SHIPPING_gte': int`
  * `'current_LIGHTNING_DEAL_lte': int`
  * `'current_LIGHTNING_DEAL_gte': int`
  * `'current_LISTPRICE_lte': int`
  * `'current_LISTPRICE_gte': int`
  * `'current_NEW_lte': int`
  * `'current_NEW_gte': int`
  * `'current_NEW_FBA_lte': int`
  * `'current_NEW_FBA_gte': int`
  * `'current_NEW_FBM_SHIPPING_lte': int`
  * `'current_NEW_FBM_SHIPPING_gte': int`
  * `'current_RATING_lte': int`
  * `'current_RATING_gte': int`
  * `'current_REFURBISHED_lte': int`
  * `'current_REFURBISHED_gte': int`
  * `'current_REFURBISHED_SHIPPING_lte': int`
  * `'current_REFURBISHED_SHIPPING_gte': int`
  * `'current_RENT_lte': int`
  * `'current_RENT_gte': int`
  * `'current_SALES_lte': int`
  * `'current_SALES_gte': int`
  * `'current_TRADE_IN_lte': int`
  * `'current_TRADE_IN_gte': int`
  * `'current_USED_lte': int`
  * `'current_USED_gte': int`
  * `'current_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'current_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'current_USED_GOOD_SHIPPING_lte': int`
  * `'current_USED_GOOD_SHIPPING_gte': int`
  * `'current_USED_NEW_SHIPPING_lte': int`
  * `'current_USED_NEW_SHIPPING_gte': int`
  * `'current_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'current_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'current_WAREHOUSE_lte': int`
  * `'current_WAREHOUSE_gte': int`
  * `'delta1_AMAZON_lte': int`
  * `'delta1_AMAZON_gte': int`
  * `'delta1_BUY_BOX_SHIPPING_lte': int`
  * `'delta1_BUY_BOX_SHIPPING_gte': int`
  * `'delta1_COLLECTIBLE_lte': int`
  * `'delta1_COLLECTIBLE_gte': int`
  * `'delta1_COUNT_COLLECTIBLE_lte': int`
  * `'delta1_COUNT_COLLECTIBLE_gte': int`
  * `'delta1_COUNT_NEW_lte': int`
  * `'delta1_COUNT_NEW_gte': int`
  * `'delta1_COUNT_REFURBISHED_lte': int`
  * `'delta1_COUNT_REFURBISHED_gte': int`
  * `'delta1_COUNT_REVIEWS_lte': int`
  * `'delta1_COUNT_REVIEWS_gte': int`
  * `'delta1_COUNT_USED_lte': int`
  * `'delta1_COUNT_USED_gte': int`
  * `'delta1_EBAY_NEW_SHIPPING_lte': int`
  * `'delta1_EBAY_NEW_SHIPPING_gte': int`
  * `'delta1_EBAY_USED_SHIPPING_lte': int`
  * `'delta1_EBAY_USED_SHIPPING_gte': int`
  * `'delta1_LIGHTNING_DEAL_lte': int`
  * `'delta1_LIGHTNING_DEAL_gte': int`
  * `'delta1_LISTPRICE_lte': int`
  * `'delta1_LISTPRICE_gte': int`
  * `'delta1_NEW_lte': int`
  * `'delta1_NEW_gte': int`
  * `'delta1_NEW_FBA_lte': int`
  * `'delta1_NEW_FBA_gte': int`
  * `'delta1_NEW_FBM_SHIPPING_lte': int`
  * `'delta1_NEW_FBM_SHIPPING_gte': int`
  * `'delta1_RATING_lte': int`
  * `'delta1_RATING_gte': int`
  * `'delta1_REFURBISHED_lte': int`
  * `'delta1_REFURBISHED_gte': int`
  * `'delta1_REFURBISHED_SHIPPING_lte': int`
  * `'delta1_REFURBISHED_SHIPPING_gte': int`
  * `'delta1_RENT_lte': int`
  * `'delta1_RENT_gte': int`
  * `'delta1_SALES_lte': int`
  * `'delta1_SALES_gte': int`
  * `'delta1_TRADE_IN_lte': int`
  * `'delta1_TRADE_IN_gte': int`
  * `'delta1_USED_lte': int`
  * `'delta1_USED_gte': int`
  * `'delta1_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'delta1_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'delta1_USED_GOOD_SHIPPING_lte': int`
  * `'delta1_USED_GOOD_SHIPPING_gte': int`
  * `'delta1_USED_NEW_SHIPPING_lte': int`
  * `'delta1_USED_NEW_SHIPPING_gte': int`
  * `'delta1_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'delta1_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'delta1_WAREHOUSE_lte': int`
  * `'delta1_WAREHOUSE_gte': int`
  * `'delta30_AMAZON_lte': int`
  * `'delta30_AMAZON_gte': int`
  * `'delta30_BUY_BOX_SHIPPING_lte': int`
  * `'delta30_BUY_BOX_SHIPPING_gte': int`
  * `'delta30_COLLECTIBLE_lte': int`
  * `'delta30_COLLECTIBLE_gte': int`
  * `'delta30_COUNT_COLLECTIBLE_lte': int`
  * `'delta30_COUNT_COLLECTIBLE_gte': int`
  * `'delta30_COUNT_NEW_lte': int`
  * `'delta30_COUNT_NEW_gte': int`
  * `'delta30_COUNT_REFURBISHED_lte': int`
  * `'delta30_COUNT_REFURBISHED_gte': int`
  * `'delta30_COUNT_REVIEWS_lte': int`
  * `'delta30_COUNT_REVIEWS_gte': int`
  * `'delta30_COUNT_USED_lte': int`
  * `'delta30_COUNT_USED_gte': int`
  * `'delta30_EBAY_NEW_SHIPPING_lte': int`
  * `'delta30_EBAY_NEW_SHIPPING_gte': int`
  * `'delta30_EBAY_USED_SHIPPING_lte': int`
  * `'delta30_EBAY_USED_SHIPPING_gte': int`
  * `'delta30_LIGHTNING_DEAL_lte': int`
  * `'delta30_LIGHTNING_DEAL_gte': int`
  * `'delta30_LISTPRICE_lte': int`
  * `'delta30_LISTPRICE_gte': int`
  * `'delta30_NEW_lte': int`
  * `'delta30_NEW_gte': int`
  * `'delta30_NEW_FBA_lte': int`
  * `'delta30_NEW_FBA_gte': int`
  * `'delta30_NEW_FBM_SHIPPING_lte': int`
  * `'delta30_NEW_FBM_SHIPPING_gte': int`
  * `'delta30_RATING_lte': int`
  * `'delta30_RATING_gte': int`
  * `'delta30_REFURBISHED_lte': int`
  * `'delta30_REFURBISHED_gte': int`
  * `'delta30_REFURBISHED_SHIPPING_lte': int`
  * `'delta30_REFURBISHED_SHIPPING_gte': int`
  * `'delta30_RENT_lte': int`
  * `'delta30_RENT_gte': int`
  * `'delta30_SALES_lte': int`
  * `'delta30_SALES_gte': int`
  * `'delta30_TRADE_IN_lte': int`
  * `'delta30_TRADE_IN_gte': int`
  * `'delta30_USED_lte': int`
  * `'delta30_USED_gte': int`
  * `'delta30_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'delta30_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'delta30_USED_GOOD_SHIPPING_lte': int`
  * `'delta30_USED_GOOD_SHIPPING_gte': int`
  * `'delta30_USED_NEW_SHIPPING_lte': int`
  * `'delta30_USED_NEW_SHIPPING_gte': int`
  * `'delta30_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'delta30_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'delta30_WAREHOUSE_lte': int`
  * `'delta30_WAREHOUSE_gte': int`
  * `'delta7_AMAZON_lte': int`
  * `'delta7_AMAZON_gte': int`
  * `'delta7_BUY_BOX_SHIPPING_lte': int`
  * `'delta7_BUY_BOX_SHIPPING_gte': int`
  * `'delta7_COLLECTIBLE_lte': int`
  * `'delta7_COLLECTIBLE_gte': int`
  * `'delta7_COUNT_COLLECTIBLE_lte': int`
  * `'delta7_COUNT_COLLECTIBLE_gte': int`
  * `'delta7_COUNT_NEW_lte': int`
  * `'delta7_COUNT_NEW_gte': int`
  * `'delta7_COUNT_REFURBISHED_lte': int`
  * `'delta7_COUNT_REFURBISHED_gte': int`
  * `'delta7_COUNT_REVIEWS_lte': int`
  * `'delta7_COUNT_REVIEWS_gte': int`
  * `'delta7_COUNT_USED_lte': int`
  * `'delta7_COUNT_USED_gte': int`
  * `'delta7_EBAY_NEW_SHIPPING_lte': int`
  * `'delta7_EBAY_NEW_SHIPPING_gte': int`
  * `'delta7_EBAY_USED_SHIPPING_lte': int`
  * `'delta7_EBAY_USED_SHIPPING_gte': int`
  * `'delta7_LIGHTNING_DEAL_lte': int`
  * `'delta7_LIGHTNING_DEAL_gte': int`
  * `'delta7_LISTPRICE_lte': int`
  * `'delta7_LISTPRICE_gte': int`
  * `'delta7_NEW_lte': int`
  * `'delta7_NEW_gte': int`
  * `'delta7_NEW_FBA_lte': int`
  * `'delta7_NEW_FBA_gte': int`
  * `'delta7_NEW_FBM_SHIPPING_lte': int`
  * `'delta7_NEW_FBM_SHIPPING_gte': int`
  * `'delta7_RATING_lte': int`
  * `'delta7_RATING_gte': int`
  * `'delta7_REFURBISHED_lte': int`
  * `'delta7_REFURBISHED_gte': int`
  * `'delta7_REFURBISHED_SHIPPING_lte': int`
  * `'delta7_REFURBISHED_SHIPPING_gte': int`
  * `'delta7_RENT_lte': int`
  * `'delta7_RENT_gte': int`
  * `'delta7_SALES_lte': int`
  * `'delta7_SALES_gte': int`
  * `'delta7_TRADE_IN_lte': int`
  * `'delta7_TRADE_IN_gte': int`
  * `'delta7_USED_lte': int`
  * `'delta7_USED_gte': int`
  * `'delta7_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'delta7_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'delta7_USED_GOOD_SHIPPING_lte': int`
  * `'delta7_USED_GOOD_SHIPPING_gte': int`
  * `'delta7_USED_NEW_SHIPPING_lte': int`
  * `'delta7_USED_NEW_SHIPPING_gte': int`
  * `'delta7_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'delta7_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'delta7_WAREHOUSE_lte': int`
  * `'delta7_WAREHOUSE_gte': int`
  * `'delta90_AMAZON_lte': int`
  * `'delta90_AMAZON_gte': int`
  * `'delta90_BUY_BOX_SHIPPING_lte': int`
  * `'delta90_BUY_BOX_SHIPPING_gte': int`
  * `'delta90_COLLECTIBLE_lte': int`
  * `'delta90_COLLECTIBLE_gte': int`
  * `'delta90_COUNT_COLLECTIBLE_lte': int`
  * `'delta90_COUNT_COLLECTIBLE_gte': int`
  * `'delta90_COUNT_NEW_lte': int`
  * `'delta90_COUNT_NEW_gte': int`
  * `'delta90_COUNT_REFURBISHED_lte': int`
  * `'delta90_COUNT_REFURBISHED_gte': int`
  * `'delta90_COUNT_REVIEWS_lte': int`
  * `'delta90_COUNT_REVIEWS_gte': int`
  * `'delta90_COUNT_USED_lte': int`
  * `'delta90_COUNT_USED_gte': int`
  * `'delta90_EBAY_NEW_SHIPPING_lte': int`
  * `'delta90_EBAY_NEW_SHIPPING_gte': int`
  * `'delta90_EBAY_USED_SHIPPING_lte': int`
  * `'delta90_EBAY_USED_SHIPPING_gte': int`
  * `'delta90_LIGHTNING_DEAL_lte': int`
  * `'delta90_LIGHTNING_DEAL_gte': int`
  * `'delta90_LISTPRICE_lte': int`
  * `'delta90_LISTPRICE_gte': int`
  * `'delta90_NEW_lte': int`
  * `'delta90_NEW_gte': int`
  * `'delta90_NEW_FBA_lte': int`
  * `'delta90_NEW_FBA_gte': int`
  * `'delta90_NEW_FBM_SHIPPING_lte': int`
  * `'delta90_NEW_FBM_SHIPPING_gte': int`
  * `'delta90_RATING_lte': int`
  * `'delta90_RATING_gte': int`
  * `'delta90_REFURBISHED_lte': int`
  * `'delta90_REFURBISHED_gte': int`
  * `'delta90_REFURBISHED_SHIPPING_lte': int`
  * `'delta90_REFURBISHED_SHIPPING_gte': int`
  * `'delta90_RENT_lte': int`
  * `'delta90_RENT_gte': int`
  * `'delta90_SALES_lte': int`
  * `'delta90_SALES_gte': int`
  * `'delta90_TRADE_IN_lte': int`
  * `'delta90_TRADE_IN_gte': int`
  * `'delta90_USED_lte': int`
  * `'delta90_USED_gte': int`
  * `'delta90_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'delta90_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'delta90_USED_GOOD_SHIPPING_lte': int`
  * `'delta90_USED_GOOD_SHIPPING_gte': int`
  * `'delta90_USED_NEW_SHIPPING_lte': int`
  * `'delta90_USED_NEW_SHIPPING_gte': int`
  * `'delta90_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'delta90_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'delta90_WAREHOUSE_lte': int`
  * `'delta90_WAREHOUSE_gte': int`
  * `'deltaLast_AMAZON_lte': int`
  * `'deltaLast_AMAZON_gte': int`
  * `'deltaLast_BUY_BOX_SHIPPING_lte': int`
  * `'deltaLast_BUY_BOX_SHIPPING_gte': int`
  * `'deltaLast_COLLECTIBLE_lte': int`
  * `'deltaLast_COLLECTIBLE_gte': int`
  * `'deltaLast_COUNT_COLLECTIBLE_lte': int`
  * `'deltaLast_COUNT_COLLECTIBLE_gte': int`
  * `'deltaLast_COUNT_NEW_lte': int`
  * `'deltaLast_COUNT_NEW_gte': int`
  * `'deltaLast_COUNT_REFURBISHED_lte': int`
  * `'deltaLast_COUNT_REFURBISHED_gte': int`
  * `'deltaLast_COUNT_REVIEWS_lte': int`
  * `'deltaLast_COUNT_REVIEWS_gte': int`
  * `'deltaLast_COUNT_USED_lte': int`
  * `'deltaLast_COUNT_USED_gte': int`
  * `'deltaLast_EBAY_NEW_SHIPPING_lte': int`
  * `'deltaLast_EBAY_NEW_SHIPPING_gte': int`
  * `'deltaLast_EBAY_USED_SHIPPING_lte': int`
  * `'deltaLast_EBAY_USED_SHIPPING_gte': int`
  * `'deltaLast_LIGHTNING_DEAL_lte': int`
  * `'deltaLast_LIGHTNING_DEAL_gte': int`
  * `'deltaLast_LISTPRICE_lte': int`
  * `'deltaLast_LISTPRICE_gte': int`
  * `'deltaLast_NEW_lte': int`
  * `'deltaLast_NEW_gte': int`
  * `'deltaLast_NEW_FBA_lte': int`
  * `'deltaLast_NEW_FBA_gte': int`
  * `'deltaLast_NEW_FBM_SHIPPING_lte': int`
  * `'deltaLast_NEW_FBM_SHIPPING_gte': int`
  * `'deltaLast_RATING_lte': int`
  * `'deltaLast_RATING_gte': int`
  * `'deltaLast_REFURBISHED_lte': int`
  * `'deltaLast_REFURBISHED_gte': int`
  * `'deltaLast_REFURBISHED_SHIPPING_lte': int`
  * `'deltaLast_REFURBISHED_SHIPPING_gte': int`
  * `'deltaLast_RENT_lte': int`
  * `'deltaLast_RENT_gte': int`
  * `'deltaLast_SALES_lte': int`
  * `'deltaLast_SALES_gte': int`
  * `'deltaLast_TRADE_IN_lte': int`
  * `'deltaLast_TRADE_IN_gte': int`
  * `'deltaLast_USED_lte': int`
  * `'deltaLast_USED_gte': int`
  * `'deltaLast_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'deltaLast_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'deltaLast_USED_GOOD_SHIPPING_lte': int`
  * `'deltaLast_USED_GOOD_SHIPPING_gte': int`
  * `'deltaLast_USED_NEW_SHIPPING_lte': int`
  * `'deltaLast_USED_NEW_SHIPPING_gte': int`
  * `'deltaLast_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'deltaLast_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'deltaLast_WAREHOUSE_lte': int`
  * `'deltaLast_WAREHOUSE_gte': int`
  * `'deltaPercent1_AMAZON_lte': int`
  * `'deltaPercent1_AMAZON_gte': int`
  * `'deltaPercent1_BUY_BOX_SHIPPING_lte': int`
  * `'deltaPercent1_BUY_BOX_SHIPPING_gte': int`
  * `'deltaPercent1_COLLECTIBLE_lte': int`
  * `'deltaPercent1_COLLECTIBLE_gte': int`
  * `'deltaPercent1_COUNT_COLLECTIBLE_lte': int`
  * `'deltaPercent1_COUNT_COLLECTIBLE_gte': int`
  * `'deltaPercent1_COUNT_NEW_lte': int`
  * `'deltaPercent1_COUNT_NEW_gte': int`
  * `'deltaPercent1_COUNT_REFURBISHED_lte': int`
  * `'deltaPercent1_COUNT_REFURBISHED_gte': int`
  * `'deltaPercent1_COUNT_REVIEWS_lte': int`
  * `'deltaPercent1_COUNT_REVIEWS_gte': int`
  * `'deltaPercent1_COUNT_USED_lte': int`
  * `'deltaPercent1_COUNT_USED_gte': int`
  * `'deltaPercent1_EBAY_NEW_SHIPPING_lte': int`
  * `'deltaPercent1_EBAY_NEW_SHIPPING_gte': int`
  * `'deltaPercent1_EBAY_USED_SHIPPING_lte': int`
  * `'deltaPercent1_EBAY_USED_SHIPPING_gte': int`
  * `'deltaPercent1_LIGHTNING_DEAL_lte': int`
  * `'deltaPercent1_LIGHTNING_DEAL_gte': int`
  * `'deltaPercent1_LISTPRICE_lte': int`
  * `'deltaPercent1_LISTPRICE_gte': int`
  * `'deltaPercent1_NEW_lte': int`
  * `'deltaPercent1_NEW_gte': int`
  * `'deltaPercent1_NEW_FBA_lte': int`
  * `'deltaPercent1_NEW_FBA_gte': int`
  * `'deltaPercent1_NEW_FBM_SHIPPING_lte': int`
  * `'deltaPercent1_NEW_FBM_SHIPPING_gte': int`
  * `'deltaPercent1_RATING_lte': int`
  * `'deltaPercent1_RATING_gte': int`
  * `'deltaPercent1_REFURBISHED_lte': int`
  * `'deltaPercent1_REFURBISHED_gte': int`
  * `'deltaPercent1_REFURBISHED_SHIPPING_lte': int`
  * `'deltaPercent1_REFURBISHED_SHIPPING_gte': int`
  * `'deltaPercent1_RENT_lte': int`
  * `'deltaPercent1_RENT_gte': int`
  * `'deltaPercent1_SALES_lte': int`
  * `'deltaPercent1_SALES_gte': int`
  * `'deltaPercent1_TRADE_IN_lte': int`
  * `'deltaPercent1_TRADE_IN_gte': int`
  * `'deltaPercent1_USED_lte': int`
  * `'deltaPercent1_USED_gte': int`
  * `'deltaPercent1_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'deltaPercent1_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'deltaPercent1_USED_GOOD_SHIPPING_lte': int`
  * `'deltaPercent1_USED_GOOD_SHIPPING_gte': int`
  * `'deltaPercent1_USED_NEW_SHIPPING_lte': int`
  * `'deltaPercent1_USED_NEW_SHIPPING_gte': int`
  * `'deltaPercent1_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'deltaPercent1_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'deltaPercent1_WAREHOUSE_lte': int`
  * `'deltaPercent1_WAREHOUSE_gte': int`
  * `'deltaPercent30_AMAZON_lte': int`
  * `'deltaPercent30_AMAZON_gte': int`
  * `'deltaPercent30_BUY_BOX_SHIPPING_lte': int`
  * `'deltaPercent30_BUY_BOX_SHIPPING_gte': int`
  * `'deltaPercent30_COLLECTIBLE_lte': int`
  * `'deltaPercent30_COLLECTIBLE_gte': int`
  * `'deltaPercent30_COUNT_COLLECTIBLE_lte': int`
  * `'deltaPercent30_COUNT_COLLECTIBLE_gte': int`
  * `'deltaPercent30_COUNT_NEW_lte': int`
  * `'deltaPercent30_COUNT_NEW_gte': int`
  * `'deltaPercent30_COUNT_REFURBISHED_lte': int`
  * `'deltaPercent30_COUNT_REFURBISHED_gte': int`
  * `'deltaPercent30_COUNT_REVIEWS_lte': int`
  * `'deltaPercent30_COUNT_REVIEWS_gte': int`
  * `'deltaPercent30_COUNT_USED_lte': int`
  * `'deltaPercent30_COUNT_USED_gte': int`
  * `'deltaPercent30_EBAY_NEW_SHIPPING_lte': int`
  * `'deltaPercent30_EBAY_NEW_SHIPPING_gte': int`
  * `'deltaPercent30_EBAY_USED_SHIPPING_lte': int`
  * `'deltaPercent30_EBAY_USED_SHIPPING_gte': int`
  * `'deltaPercent30_LIGHTNING_DEAL_lte': int`
  * `'deltaPercent30_LIGHTNING_DEAL_gte': int`
  * `'deltaPercent30_LISTPRICE_lte': int`
  * `'deltaPercent30_LISTPRICE_gte': int`
  * `'deltaPercent30_NEW_lte': int`
  * `'deltaPercent30_NEW_gte': int`
  * `'deltaPercent30_NEW_FBA_lte': int`
  * `'deltaPercent30_NEW_FBA_gte': int`
  * `'deltaPercent30_NEW_FBM_SHIPPING_lte': int`
  * `'deltaPercent30_NEW_FBM_SHIPPING_gte': int`
  * `'deltaPercent30_RATING_lte': int`
  * `'deltaPercent30_RATING_gte': int`
  * `'deltaPercent30_REFURBISHED_lte': int`
  * `'deltaPercent30_REFURBISHED_gte': int`
  * `'deltaPercent30_REFURBISHED_SHIPPING_lte': int`
  * `'deltaPercent30_REFURBISHED_SHIPPING_gte': int`
  * `'deltaPercent30_RENT_lte': int`
  * `'deltaPercent30_RENT_gte': int`
  * `'deltaPercent30_SALES_lte': int`
  * `'deltaPercent30_SALES_gte': int`
  * `'deltaPercent30_TRADE_IN_lte': int`
  * `'deltaPercent30_TRADE_IN_gte': int`
  * `'deltaPercent30_USED_lte': int`
  * `'deltaPercent30_USED_gte': int`
  * `'deltaPercent30_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'deltaPercent30_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'deltaPercent30_USED_GOOD_SHIPPING_lte': int`
  * `'deltaPercent30_USED_GOOD_SHIPPING_gte': int`
  * `'deltaPercent30_USED_NEW_SHIPPING_lte': int`
  * `'deltaPercent30_USED_NEW_SHIPPING_gte': int`
  * `'deltaPercent30_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'deltaPercent30_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'deltaPercent30_WAREHOUSE_lte': int`
  * `'deltaPercent30_WAREHOUSE_gte': int`
  * `'deltaPercent7_AMAZON_lte': int`
  * `'deltaPercent7_AMAZON_gte': int`
  * `'deltaPercent7_BUY_BOX_SHIPPING_lte': int`
  * `'deltaPercent7_BUY_BOX_SHIPPING_gte': int`
  * `'deltaPercent7_COLLECTIBLE_lte': int`
  * `'deltaPercent7_COLLECTIBLE_gte': int`
  * `'deltaPercent7_COUNT_COLLECTIBLE_lte': int`
  * `'deltaPercent7_COUNT_COLLECTIBLE_gte': int`
  * `'deltaPercent7_COUNT_NEW_lte': int`
  * `'deltaPercent7_COUNT_NEW_gte': int`
  * `'deltaPercent7_COUNT_REFURBISHED_lte': int`
  * `'deltaPercent7_COUNT_REFURBISHED_gte': int`
  * `'deltaPercent7_COUNT_REVIEWS_lte': int`
  * `'deltaPercent7_COUNT_REVIEWS_gte': int`
  * `'deltaPercent7_COUNT_USED_lte': int`
  * `'deltaPercent7_COUNT_USED_gte': int`
  * `'deltaPercent7_EBAY_NEW_SHIPPING_lte': int`
  * `'deltaPercent7_EBAY_NEW_SHIPPING_gte': int`
  * `'deltaPercent7_EBAY_USED_SHIPPING_lte': int`
  * `'deltaPercent7_EBAY_USED_SHIPPING_gte': int`
  * `'deltaPercent7_LIGHTNING_DEAL_lte': int`
  * `'deltaPercent7_LIGHTNING_DEAL_gte': int`
  * `'deltaPercent7_LISTPRICE_lte': int`
  * `'deltaPercent7_LISTPRICE_gte': int`
  * `'deltaPercent7_NEW_lte': int`
  * `'deltaPercent7_NEW_gte': int`
  * `'deltaPercent7_NEW_FBA_lte': int`
  * `'deltaPercent7_NEW_FBA_gte': int`
  * `'deltaPercent7_NEW_FBM_SHIPPING_lte': int`
  * `'deltaPercent7_NEW_FBM_SHIPPING_gte': int`
  * `'deltaPercent7_RATING_lte': int`
  * `'deltaPercent7_RATING_gte': int`
  * `'deltaPercent7_REFURBISHED_lte': int`
  * `'deltaPercent7_REFURBISHED_gte': int`
  * `'deltaPercent7_REFURBISHED_SHIPPING_lte': int`
  * `'deltaPercent7_REFURBISHED_SHIPPING_gte': int`
  * `'deltaPercent7_RENT_lte': int`
  * `'deltaPercent7_RENT_gte': int`
  * `'deltaPercent7_SALES_lte': int`
  * `'deltaPercent7_SALES_gte': int`
  * `'deltaPercent7_TRADE_IN_lte': int`
  * `'deltaPercent7_TRADE_IN_gte': int`
  * `'deltaPercent7_USED_lte': int`
  * `'deltaPercent7_USED_gte': int`
  * `'deltaPercent7_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'deltaPercent7_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'deltaPercent7_USED_GOOD_SHIPPING_lte': int`
  * `'deltaPercent7_USED_GOOD_SHIPPING_gte': int`
  * `'deltaPercent7_USED_NEW_SHIPPING_lte': int`
  * `'deltaPercent7_USED_NEW_SHIPPING_gte': int`
  * `'deltaPercent7_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'deltaPercent7_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'deltaPercent7_WAREHOUSE_lte': int`
  * `'deltaPercent7_WAREHOUSE_gte': int`
  * `'deltaPercent90_AMAZON_lte': int`
  * `'deltaPercent90_AMAZON_gte': int`
  * `'deltaPercent90_BUY_BOX_SHIPPING_lte': int`
  * `'deltaPercent90_BUY_BOX_SHIPPING_gte': int`
  * `'deltaPercent90_COLLECTIBLE_lte': int`
  * `'deltaPercent90_COLLECTIBLE_gte': int`
  * `'deltaPercent90_COUNT_COLLECTIBLE_lte': int`
  * `'deltaPercent90_COUNT_COLLECTIBLE_gte': int`
  * `'deltaPercent90_COUNT_NEW_lte': int`
  * `'deltaPercent90_COUNT_NEW_gte': int`
  * `'deltaPercent90_COUNT_REFURBISHED_lte': int`
  * `'deltaPercent90_COUNT_REFURBISHED_gte': int`
  * `'deltaPercent90_COUNT_REVIEWS_lte': int`
  * `'deltaPercent90_COUNT_REVIEWS_gte': int`
  * `'deltaPercent90_COUNT_USED_lte': int`
  * `'deltaPercent90_COUNT_USED_gte': int`
  * `'deltaPercent90_EBAY_NEW_SHIPPING_lte': int`
  * `'deltaPercent90_EBAY_NEW_SHIPPING_gte': int`
  * `'deltaPercent90_EBAY_USED_SHIPPING_lte': int`
  * `'deltaPercent90_EBAY_USED_SHIPPING_gte': int`
  * `'deltaPercent90_LIGHTNING_DEAL_lte': int`
  * `'deltaPercent90_LIGHTNING_DEAL_gte': int`
  * `'deltaPercent90_LISTPRICE_lte': int`
  * `'deltaPercent90_LISTPRICE_gte': int`
  * `'deltaPercent90_NEW_lte': int`
  * `'deltaPercent90_NEW_gte': int`
  * `'deltaPercent90_NEW_FBA_lte': int`
  * `'deltaPercent90_NEW_FBA_gte': int`
  * `'deltaPercent90_NEW_FBM_SHIPPING_lte': int`
  * `'deltaPercent90_NEW_FBM_SHIPPING_gte': int`
  * `'deltaPercent90_RATING_lte': int`
  * `'deltaPercent90_RATING_gte': int`
  * `'deltaPercent90_REFURBISHED_lte': int`
  * `'deltaPercent90_REFURBISHED_gte': int`
  * `'deltaPercent90_REFURBISHED_SHIPPING_lte': int`
  * `'deltaPercent90_REFURBISHED_SHIPPING_gte': int`
  * `'deltaPercent90_RENT_lte': int`
  * `'deltaPercent90_RENT_gte': int`
  * `'deltaPercent90_SALES_lte': int`
  * `'deltaPercent90_SALES_gte': int`
  * `'deltaPercent90_TRADE_IN_lte': int`
  * `'deltaPercent90_TRADE_IN_gte': int`
  * `'deltaPercent90_USED_lte': int`
  * `'deltaPercent90_USED_gte': int`
  * `'deltaPercent90_USED_ACCEPTABLE_SHIPPING_lte': int`
  * `'deltaPercent90_USED_ACCEPTABLE_SHIPPING_gte': int`
  * `'deltaPercent90_USED_GOOD_SHIPPING_lte': int`
  * `'deltaPercent90_USED_GOOD_SHIPPING_gte': int`
  * `'deltaPercent90_USED_NEW_SHIPPING_lte': int`
  * `'deltaPercent90_USED_NEW_SHIPPING_gte': int`
  * `'deltaPercent90_USED_VERY_GOOD_SHIPPING_lte': int`
  * `'deltaPercent90_USED_VERY_GOOD_SHIPPING_gte': int`
  * `'deltaPercent90_WAREHOUSE_lte': int`
  * `'deltaPercent90_WAREHOUSE_gte': int`
  * `'department': str`
  * `'edition': str`
  * `'fbaFees_lte': int`
  * `'fbaFees_gte': int`
  * `'format': str`
  * `'genre': str`
  * `'hasParentASIN': bool`
  * `'hasReviews': bool`
  * `'hazardousMaterialType_lte': int`
  * `'hazardousMaterialType_gte': int`
  * `'isAdultProduct': bool`
  * `'isEligibleForSuperSaverShipping': bool`
  * `'isEligibleForTradeIn': bool`
  * `'isHighestOffer': bool`
  * `'isHighest_AMAZON': bool`
  * `'isHighest_BUY_BOX_SHIPPING': bool`
  * `'isHighest_COLLECTIBLE': bool`
  * `'isHighest_COUNT_COLLECTIBLE': bool`
  * `'isHighest_COUNT_NEW': bool`
  * `'isHighest_COUNT_REFURBISHED': bool`
  * `'isHighest_COUNT_REVIEWS': bool`
  * `'isHighest_COUNT_USED': bool`
  * `'isHighest_EBAY_NEW_SHIPPING': bool`
  * `'isHighest_EBAY_USED_SHIPPING': bool`
  * `'isHighest_LIGHTNING_DEAL': bool`
  * `'isHighest_LISTPRICE': bool`
  * `'isHighest_NEW': bool`
  * `'isHighest_NEW_FBA': bool`
  * `'isHighest_NEW_FBM_SHIPPING': bool`
  * `'isHighest_RATING': bool`
  * `'isHighest_REFURBISHED': bool`
  * `'isHighest_REFURBISHED_SHIPPING': bool`
  * `'isHighest_RENT': bool`
  * `'isHighest_SALES': bool`
  * `'isHighest_TRADE_IN': bool`
  * `'isHighest_USED': bool`
  * `'isHighest_USED_ACCEPTABLE_SHIPPING': bool`
  * `'isHighest_USED_GOOD_SHIPPING': bool`
  * `'isHighest_USED_NEW_SHIPPING': bool`
  * `'isHighest_USED_VERY_GOOD_SHIPPING': bool`
  * `'isHighest_WAREHOUSE': bool`
  * `'isLowestOffer': bool`
  * `'isLowest_AMAZON': bool`
  * `'isLowest_BUY_BOX_SHIPPING': bool`
  * `'isLowest_COLLECTIBLE': bool`
  * `'isLowest_COUNT_COLLECTIBLE': bool`
  * `'isLowest_COUNT_NEW': bool`
  * `'isLowest_COUNT_REFURBISHED': bool`
  * `'isLowest_COUNT_REVIEWS': bool`
  * `'isLowest_COUNT_USED': bool`
  * `'isLowest_EBAY_NEW_SHIPPING': bool`
  * `'isLowest_EBAY_USED_SHIPPING': bool`
  * `'isLowest_LIGHTNING_DEAL': bool`
  * `'isLowest_LISTPRICE': bool`
  * `'isLowest_NEW': bool`
  * `'isLowest_NEW_FBA': bool`
  * `'isLowest_NEW_FBM_SHIPPING': bool`
  * `'isLowest_RATING': bool`
  * `'isLowest_REFURBISHED': bool`
  * `'isLowest_REFURBISHED_SHIPPING': bool`
  * `'isLowest_RENT': bool`
  * `'isLowest_SALES': bool`
  * `'isLowest_TRADE_IN': bool`
  * `'isLowest_USED': bool`
  * `'isLowest_USED_ACCEPTABLE_SHIPPING': bool`
  * `'isLowest_USED_GOOD_SHIPPING': bool`
  * `'isLowest_USED_NEW_SHIPPING': bool`
  * `'isLowest_USED_VERY_GOOD_SHIPPING': bool`
  * `'isLowest_WAREHOUSE': bool`
  * `'isPrimeExclusive': bool`
  * `'isSNS': bool`
  * `'label': str`
  * `'languages': str`
  * `'lastOffersUpdate_lte': int`
  * `'lastOffersUpdate_gte': int`
  * `'lastPriceChange_lte': int`
  * `'lastPriceChange_gte': int`
  * `'lastRatingUpdate_lte': int`
  * `'lastRatingUpdate_gte': int`
  * `'lastUpdate_lte': int`
  * `'lastUpdate_gte': int`
  * `'lightningEnd_lte': int`
  * `'lightningEnd_gte': int`
  * `'lightningStart_lte': int`
  * `'lightningStart_gte': int`
  * `'listedSince_lte': int`
  * `'listedSince_gte': int`
  * `'manufacturer': str`
  * `'model': str`
  * `'newPriceIsMAP': bool`
  * `'nextUpdate_lte': int`
  * `'nextUpdate_gte': int`
  * `'numberOfItems_lte': int`
  * `'numberOfItems_gte': int`
  * `'numberOfPages_lte': int`
  * `'numberOfPages_gte': int`
  * `'numberOfTrackings_lte': int`
  * `'numberOfTrackings_gte': int`
  * `'offerCountFBA_lte': int`
  * `'offerCountFBA_gte': int`
  * `'offerCountFBM_lte': int`
  * `'offerCountFBM_gte': int`
  * `'outOfStockPercentageInInterval_lte': int`
  * `'outOfStockPercentageInInterval_gte': int`
  * `'packageDimension_lte': int`
  * `'packageDimension_gte': int`
  * `'packageHeight_lte': int`
  * `'packageHeight_gte': int`
  * `'packageLength_lte': int`
  * `'packageLength_gte': int`
  * `'packageQuantity_lte': int`
  * `'packageQuantity_gte': int`
  * `'packageWeight_lte': int`
  * `'packageWeight_gte': int`
  * `'packageWidth_lte': int`
  * `'packageWidth_gte': int`
  * `'partNumber': str`
  * `'platform': str`
  * `'productGroup': str`
  * `'productType': int`
  * `'promotions': int`
  * `'publicationDate_lte': int`
  * `'publicationDate_gte': int`
  * `'publisher': str`
  * `'releaseDate_lte': int`
  * `'releaseDate_gte': int`
  * `'rootCategory': int`
  * `'sellerIds': str`
  * `'sellerIdsLowestFBA': str`
  * `'sellerIdsLowestFBM': str`
  * `'size': str`
  * `'salesRankDrops180_lte': int`
  * `'salesRankDrops180_gte': int`
  * `'salesRankDrops90_lte': int`
  * `'salesRankDrops90_gte': int`
  * `'salesRankDrops30_lte': int`
  * `'salesRankDrops30_gte': int`
  * `'sort': list`
  * `'stockAmazon_lte': int`
  * `'stockAmazon_gte': int`
  * `'stockBuyBox_lte': int`
  * `'stockBuyBox_gte': int`
  * `'studio': str`
  * `'title': str`
  * `'title_flag': str`
  * `'trackingSince_lte': int`
  * `'trackingSince_gte': int`
  * `'type': str`
  * `'mpn': str`
  * `'outOfStockPercentage90_lte': int`
  * `'outOfStockPercentage90_gte': int`
  * `'categories_include': int`
  * `'categories_exclude': int`
* domain (*str, default: 'US'*) – One of the following Amazon domains: RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX.
* wait (*bool, default: True*) – Wait available token before doing effective query.

**Returns:**

List of ASINs matching the product parameters.

**Return type:**

list

**Notes**

When using the `'sort'` key in the `product_parms` parameter, use a compatible key along with the type of sort. For example: `["current_SALES", "asc"]`

**Examples**

Query for all of Jim Butcher’s books using the synchronous `keepa.Keepa` class. Sort by current sales

\>\>\> import keepa
\>\>\> api \= keepa.Keepa('\<ENTER\_ACTUAL\_KEY\_HERE\>')
\>\>\> product\_parms \= {
...     'author': 'jim butcher',
...     'sort': \`\`\["current\_SALES", "asc"\]\`\`,
}
\>\>\> asins \= api.product\_finder(product\_parms)
\>\>\> asins
\['B000HRMAR2',
 '0578799790',
 'B07PW1SVHM',
...
 'B003MXM744',
 '0133235750',
 'B01MXXLJPZ'\]

Query for all of Jim Butcher’s books using the asynchronous `keepa.AsyncKeepa` class.

\>\>\> **import** asyncio
\>\>\> **import** keepa
\>\>\> product\_parms **\=** **{**'author'**:** 'jim butcher'**}**
\>\>\> **async** **def** main**():**
...    key **\=** '\<REAL\_KEEPA\_KEY\>'
...    api **\=** **await** keepa**.**AsyncKeepa**().**create**(**key**)**
...    **return** **await** api**.**product\_finder**(**product\_parms**)**
\>\>\> asins **\=** asyncio**.**run**(**main**())**
\>\>\> asins
*\['B000HRMAR2',*
 *'0578799790',*
 *'B07PW1SVHM',*
*...*
 *'B003MXM744',*
 *'0133235750',*
 *'B01MXXLJPZ'\]*

**query(*items*, *stats=None*, *domain='US'*, *history=True*, *offers=None*, *update=None*, *to\_datetime=True*, *rating=False*, *out\_of\_stock\_as\_nan=True*, *stock=False*, *product\_code\_is\_asin=True*, *progress\_bar=True*, *buybox=False*, *wait=True*, *days=None*, *only\_live\_offers=None*, *raw=False*)**

Perform a product query of a list, array, or single ASIN.

Returns a list of product data with one entry for each product.

**Parameters:**

* items (*str, list, np.ndarray*) – A list, array, or single asin, UPC, EAN, or ISBN-13 identifying a product. ASINs should be 10 characters and match a product on Amazon. Items not matching Amazon product or duplicate Items will return no data. When using non-ASIN items, set product\_code\_is\_asin to False
* stats (*int or date, optional*) –
  No extra token cost. If specified the product object will have a stats field with quick access to current prices, min/max prices and the weighted mean values. If the offers parameter was used it will also provide stock counts and buy box information.
  You can provide the stats parameter in two forms:
  Last x days (positive integer value): calculates the stats of the last x days, where x is the value of the stats parameter. Interval: You can provide a date range for the stats calculation. You can specify the range via two timestamps (unix epoch time milliseconds) or two date strings (ISO8601, with or without time in UTC).
* domain (*str, optional*) – One of the following Amazon domains: RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX Defaults to US.
* offers (*int, optional*) – Adds available offers to product data. Default 0\. Must be between 20 and 100\.
* update (*int, optional*) – if data is older than the input integer, keepa will update their database and return live data. If set to 0 (live data), request may cost an additional token. Default None
* history (*bool, optional*) – When set to True includes the price, sales, and offer history of a product. Set to False to reduce request time if data is not required. Default True
* rating (*bool, optional*) – When set to to True, includes the existing RATING and COUNT\_REVIEWS history of the csv field. Default False
* to\_datetime (*bool, optional*) – Modifies numpy minutes to datetime.datetime values. Default True.
* out\_of\_stock\_as\_nan (*bool, optional*) – When True, prices are NAN when price category is out of stock. When False, prices are \-0.01 Default True
* stock (*bool, optional*) – Can only be used if the offers parameter is also True. If True, the stock will be collected for all retrieved live offers. Note: We can only determine stock up 10 qty. Stock retrieval takes additional time, expect the request to take longer. Existing stock history will be included whether or not the stock parameter is used.
* product\_code\_is\_asin (*bool, optional*) – The type of product code you are requesting. True when product code is an ASIN, an Amazon standard identification number, or ‘code’, for UPC, EAN, or ISBN-13 codes.
* progress\_bar (*bool, optional*) – Display a progress bar using `tqdm`. Defaults to `True`.
* buybox (*bool, optional*) –
  Additional token cost: 2 per product). When true the product and statistics object will include all available buy box related data:
  * current price, price history, and statistical values
  * buyBoxSellerIdHistory
  * all buy box fields in the statistics object
* The buybox parameter does not trigger a fresh data collection. If the offers parameter is used the buybox parameter is ignored, as the offers parameter also provides access to all buy box related data. To access the statistics object the stats parameter is required.
* wait (*bool, optional*) – Wait available token before doing effective query, Defaults to `True`.
* only\_live\_offers (*bool, optional*) – If set to True, the product object will only include live marketplace offers (when used in combination with the offers parameter). If you do not need historical offers use this to have them removed from the response. This can improve processing time and considerably decrease the size of the response. Default None
* days (*int, optional*) – Any positive integer value. If specified and has positive value X the product object will limit all historical data to the recent X days. This includes the csv, buyBoxSellerIdHistory, salesRanks, offers and offers.offerCSV fields. If you do not need old historical data use this to have it removed from the response. This can improve processing time and considerably decrease the size of the response. The parameter does not use calendar days \- so 1 day equals the last 24 hours. The oldest data point of each field may have a date value which is out of the specified range. This means the value of the field has not changed since that date and is still active. Default `None`
* raw (*bool, optional*) – When `True`, return the raw request response. This is only available in the non-async class.

**Returns:**

List of products when `raw=False`. Each product within the list is a dictionary. The keys of each item may vary, so see the keys within each product for further details.

Each product should contain at a minimum a “data” key containing a formatted dictionary. For the available fields see the notes section

When `raw=True`, a list of unparsed responses are returned as **`requests.models.Response`**.

See: [https://keepa.com/\#\!discuss/t/product-object/116](https://keepa.com/#!discuss/t/product-object/116)

**Return type:**

list

**Notes**

The following are some of the fields a product dictionary. For a full list and description, please see: [product-object](https://keepa.com/#!discuss/t/product-object/116)

**AMAZON**

Amazon price history

**NEW**

Marketplace/3rd party New price history \- Amazon is considered to be part of the marketplace as well, so if Amazon has the overall lowest new (\!) price, the marketplace new price in the corresponding time interval will be identical to the Amazon price (except if there is only one marketplace offer). Shipping and Handling costs not included\!

**USED**

Marketplace/3rd party Used price history

**SALES**

Sales Rank history. Not every product has a Sales Rank.

**LISTPRICE**

List Price history

**COLLECTIBLE**

Collectible Price history

**REFURBISHED**

Refurbished Price history

**NEW\_FBM\_SHIPPING**

3rd party (not including Amazon) New price history including shipping costs, only fulfilled by merchant (FBM).

**LIGHTNING\_DEAL**

3rd party (not including Amazon) New price history including shipping costs, only fulfilled by merchant (FBM).

**WAREHOUSE**

Amazon Warehouse Deals price history. Mostly of used condition, rarely new.

**NEW\_FBA**

Price history of the lowest 3rd party (not including Amazon/Warehouse) New offer that is fulfilled by Amazon

**COUNT\_NEW**

New offer count history

**COUNT\_USED**

Used offer count history

**COUNT\_REFURBISHED**

Refurbished offer count history

**COUNT\_COLLECTIBLE**

Collectible offer count history

**RATING**

The product’s rating history. A rating is an integer from 0 to 50 (e.g. 45 \= 4.5 stars)

**COUNT\_REVIEWS**

The product’s review count history.

**BUY\_BOX\_SHIPPING**

The price history of the buy box. If no offer qualified for the buy box the price has the value \-1. Including shipping costs.

**USED\_NEW\_SHIPPING**

“Used \- Like New” price history including shipping costs.

**USED\_VERY\_GOOD\_SHIPPING**

“Used \- Very Good” price history including shipping costs.

**USED\_GOOD\_SHIPPING**

“Used \- Good” price history including shipping costs.

**USED\_ACCEPTABLE\_SHIPPING**

“Used \- Acceptable” price history including shipping costs.

**COLLECTIBLE\_NEW\_SHIPPING**

“Collectible \- Like New” price history including shipping costs.

**COLLECTIBLE\_VERY\_GOOD\_SHIPPING**

“Collectible \- Very Good” price history including shipping costs.

**COLLECTIBLE\_GOOD\_SHIPPING**

“Collectible \- Good” price history including shipping costs.

**COLLECTIBLE\_ACCEPTABLE\_SHIPPING**

“Collectible \- Acceptable” price history including shipping costs.

**REFURBISHED\_SHIPPING**

Refurbished price history including shipping costs.

**TRADE\_IN**

The trade in price history. Amazon trade-in is not available for every locale.

**BUY\_BOX\_SHIPPING**

The price history of the buy box. If no offer qualified for the buy box the price has the value \-1. Including shipping costs. The `buybox` parameter must be True for this field to be in the data.

**Examples**

Query for product with ASIN `'B0088PUEPK'` using the synchronous keepa interface.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> response **\=** api**.**query**(**'B0088PUEPK'**)**
\>\>\> response**\[0\]\[**'title'**\]**
*'Western Digital 1TB WD Blue PC Internal Hard Drive HDD \- 7200 RPM,*
*SATA 6 Gb/s, 64 MB Cache, 3.5" \- WD10EZEX'*

Query for product with ASIN `'B0088PUEPK'` using the asynchronous keepa interface.

\>\>\> **import** asyncio
\>\>\> **import** keepa
\>\>\> **async** **def** main**():**
...    key **\=** '\<REAL\_KEEPA\_KEY\>'
...    api **\=** **await** keepa**.**AsyncKeepa**().**create**(**key**)**
...    **return** **await** api**.**query**(**'B0088PUEPK'**)**
\>\>\> response **\=** asyncio**.**run**(**main**())**
\>\>\> response**\[0\]\[**'title'**\]**
*'Western Digital 1TB WD Blue PC Internal Hard Drive HDD \- 7200 RPM,*
*SATA 6 Gb/s, 64 MB Cache, 3.5" \- WD10EZEX'*

**search\_for\_categories(*searchterm*, *domain='US'*, *wait=True*) → list**

Search for categories from Amazon.

**Parameters:**

* searchterm (*str*) – Input search term.
* domain (*str, default: 'US'*) – Amazon locale you want to access. Must be one of the following RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX Default US.
* wait (*bool, default: True*) – Wait available token before doing effective query. Defaults to `True`.

**Returns:**

The response contains a categories list with all matching categories.

**Return type:**

list

**Examples**

Print all categories from science.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> categories **\=** api**.**search\_for\_categories**(**'science'**)**
\>\>\> **for** cat\_id **in** categories**:**
...    print**(**cat\_id**,** categories**\[**cat\_id**\]\[**'name'**\])**
*9091159011 Behavioral Sciences*
*8407535011 Fantasy, Horror & Science Fiction*
*8407519011 Sciences & Technology*
*12805 Science & Religion*
*13445 Astrophysics & Space Science*
*12038 Science Fiction & Fantasy*
*3207 Science, Nature & How It Works*
*144 Science Fiction & Fantasy*

**seller\_query(*seller\_id*, *domain='US'*, *to\_datetime=True*, *storefront=False*, *update=None*, *wait=True*)**

Receive seller information for a given seller id.

If a seller is not found no tokens will be consumed.

Token cost: 1 per requested seller

**Parameters:**

* seller\_id (*str or list*) – The seller id of the merchant you want to request. For batch requests, you may submit a list of 100 seller\_ids. The seller id can also be found on Amazon on seller profile pages in the seller parameter of the URL as well as in the offers results from a product query.
* domain (*str, optional*) – One of the following Amazon domains: RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX Defaults to US.
* storefront (*bool, optional*) – If specified the seller object will contain additional information about what items the seller is listing on Amazon. This includes a list of ASINs as well as the total amount of items the seller has listed. The following seller object fields will be set if data is available: asinList, asinListLastSeen, totalStorefrontAsinsCSV. If no data is available no additional tokens will be consumed. The ASIN list can contain up to 100,000 items. As using the storefront parameter does not trigger any new collection it does not increase the processing time of the request, though the response may be much bigger in size. The total storefront ASIN count will not be updated, only historical data will be provided (when available).
* update (*int, optional*) –
  Positive integer value. If the last live data collection from the Amazon storefront page is older than update hours force a new collection. Use this parameter in conjunction with the storefront parameter. Token cost will only be applied if a new collection is triggered.
  Using this parameter you can achieve the following:
  * Retrieve data from Amazon: a storefront ASIN list containing up to 2,400 ASINs, in addition to all ASINs already collected through our database.
  * Force a refresh: Always retrieve live data with the value 0\.
  * Retrieve the total number of listings of this seller: the totalStorefrontAsinsCSV field of the seller object will be updated.
* wait (*bool, optional*) – Wait available token before doing effective query. Defaults to `True`.

**Returns:**

Dictionary containing one entry per input `seller_id`.

**Return type:**

dict

**Examples**

Return the information from seller `'A2L77EE7U53NWQ'`.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> seller\_info **\=** api**.**seller\_query**(**'A2L77EE7U53NWQ'**,** 'US'**)**
\>\>\> seller\_info**\[**'A2L77EE7U53NWQ'**\]\[**'sellerName'**\]**
*'Amazon Warehouse'*

**Notes**

Seller data is not available for Amazon China.

***property*** **time\_to\_refill*: float***

Return the time to refill in seconds.

**Examples**

Return the time to refill. If you have tokens available, this time should be 0.0 seconds.

\>\>\> **import** keepa
\>\>\> key **\=** '\<REAL\_KEEPA\_KEY\>'
\>\>\> api **\=** keepa**.**Keepa**(**key**)**
\>\>\> api**.**time\_to\_refill
*0.0*

**update\_status()**

Update available tokens.

**wait\_for\_tokens()**

Check if there are any remaining tokens and waits if none are available.
 On this page

* [**`Keepa`](https://keepaapi.readthedocs.io/en/latest/api_methods.html#keepa.Keepa)**

 [Edit this page](https://github.com/akaszynski/keepa/edit/master/doc/api_methods.rst)
© Copyright 2018-2023, Alex Kaszynski.
Built with the [PyData Sphinx Theme](https://pydata-sphinx-theme.readthedocs.io/en/stable/index.html) 0.12.0.
Created using [Sphinx](http://sphinx-doc.org/) 6.1.2.
Read the Docs latest
