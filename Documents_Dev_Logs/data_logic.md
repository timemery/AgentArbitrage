# Agent Arbitrage Data Logic and Dashboard Column Reference

This document serves as the definitive reference for the data logic, calculations, and formulas used to populate the Agent Arbitrage deals dashboard. Its purpose is to ensure that the functionality of each column is clearly understood, preventing the loss of complex logic during future development.

## Core Architectural Concepts

*   **Data Pipeline**: The current system uses a multi-stage data pipeline. Data is fetched from the Keepa API, processed through a series of calculations and enrichments, and then stored in a persistent SQLite database (`deals.db`). The dashboard's API (`/api/deals`) reads from this database.
*   **Separation of Concerns**: A key architectural principle is the separation of data processing from presentation. The backend is responsible for providing raw, unformatted data. The frontend (JavaScript in `dashboard.html`) is responsible for all formatting (e.g., adding currency symbols, commas, percentage signs).
*   **Data Sanitization**: When data is saved to the SQLite database, column names from `headers.json` are "sanitized." This process (in `db_utils.py`) replaces spaces, hyphens, and other special characters with underscores. This is a critical transformation, as the frontend JavaScript must use the sanitized key to access the data.

## Dashboard Column Breakdown

---

### **Book Details**

#### **Title**

*   **Source**: Keepa API (`product['title']`)
*   **Logic**: Direct mapping.
*   **Notes**: The full title is stored in the database. The UI truncates it to 120px for display.

#### **Genre**

*   **Source**: Keepa API (`product['categoryTree']`) -> "Categories - Sub" column.
*   **Logic**: The backend extracts the sub-category path. The frontend then performs two transformations for display:
    1.  It maps the sanitized data key `Categories___Sub` to the display name "Genre".
    2.  It strips the `Subjects, ` prefix from the string (e.g., "Subjects, Literature & Fiction" becomes "Literature & Fiction").
    3.  If the result is empty, it displays "No Subject Listed".

---

### **Sales Rank & Seasonality**

#### **Current (Sales Rank)**

*   **Source**: Keepa API (`product['stats']['current'][SALES]`) where `SALES` is the index for sales rank.
*   **Logic**: Direct mapping of the most recent sales rank.
*   **Formatting Issue**: The incorrect sorting behavior (e.g., `1,609,881` vs. `1`) is due to the database column being typed as `TEXT` instead of `INTEGER`. The sorting is lexicographical, not numerical.
    *   **Fix**: The `db_utils.py` schema creation logic needs to be corrected to ensure this column is `INTEGER`.

#### **Avg. Rank (365-day Avg.)**

*   **Source**: Keepa API (`product['stats']['avg365'][SALES]`)
*   **Logic**: Direct mapping of Keepa's pre-calculated 365-day average sales rank.
*   **Formatting Issue**: Same as "Current" rank, this is a `TEXT` sorting issue.

#### **Season**

*   **Source**: Combination of product metadata (Title, Genre, Manufacturer) and AI reasoning.
*   **Function**: `seasonality_classifier.py -> classify_seasonality()`
*   **Logic (Pre-DB logic to be restored)**:
    1.  **Keyword Heuristics**: The function first checks the book's title and categories against a predefined list of keywords in `seasonal_config.py` (e.g., "Christmas", "Gardening", "Textbook").
    2.  **AI Fallback**: If no keyword match is found, the function formats the metadata and queries an external XAI (Explainable AI) model to determine if the book has a seasonal sales pattern.
    3.  **Default**: If neither method finds a season, it defaults to "Year-round".

#### **Sells**

*   **Source**: The output of the "Season" column.
*   **Function**: `seasonality_classifier.py -> get_sells_period()`
*   **Logic (Pre-DB logic to be restored)**:
    1.  This function acts as a simple mapping. It takes the season name (e.g., "Tax Season") and returns a human-readable date range (e.g., "Feb - Apr").
    2.  For "Year-round" books, it returns "All Year".
    3.  This provides a more intuitive understanding of when the book is expected to sell.

---

### **Seller Details**

#### **Name (Seller Name)**

*   **Source**: Keepa API (`product['offers']` -> seller data).
*   **Logic**: This logic identifies the seller of the "Best Price" offer, which is not necessarily the Buy Box seller.
*   **Notes**: UI truncates to 120px.

#### **Seller Score**

*   **Source**: Keepa API (seller rating and review count).
*   **Logic**: A quality score is calculated based on the seller's feedback rating and the total number of ratings. A higher number of ratings provides more confidence in the score. A "New Seller" is one with no rating history.

---

### **Deal Details & Current Best Price**

#### **Now (Current Price)**

*   **Source**: Keepa API (`product['offers']`).
*   **Logic (Pre-DB logic to be restored)**:
    1.  This represents the **lowest currently available USED price from a qualified seller**.
    2.  The logic iterates through all *live* offers.
    3.  It filters out sellers who do not meet a minimum quality score, especially for books in "Acceptable" or "Collectible" condition.
    4.  The `"-"` indicates that no live offer from a qualified seller could be found, which should be rare but is possible if all current offers are from very new or poorly-rated sellers.

#### **Condition**

*   **Source**: Keepa API (`product['offers']`).
*   **Logic**: Displays the condition of the offer that corresponds to the "Now" price.

---

### **Profit Estimates & Recommended Listing Price**

#### **List at (Peak Inferred Sale Price)**

*   **Source**: Keepa API (historical price and sales rank data).
*   **Function**: `stable_calculations.py -> infer_sale_events()` and related analytics.
*   **Logic (Pre-DB logic to be restored)**: This is one of the most complex and important calculations.
    1.  **Infer Sale Events**: The system analyzes 2 years of historical data, looking for patterns that indicate a sale occurred (a drop in offer count followed by a drop in sales rank within 72 hours).
    2.  **Price at Sale**: The price at the time of the inferred sale is recorded.
    3.  **Outlier Rejection**: A symmetrical Interquartile Range (IQR) is used to discard both anomalously high and low inferred sale prices, cleaning the data.
    4.  **Peak/Trough Analysis**: The cleaned sale prices are grouped by month to identify "peak" and "trough" selling seasons based on the `mean` sale price in those periods.
    5.  **Final Value**: "List at" is the **mean inferred sale price during the peak season**. This gives the user an ambitious but data-backed target listing price.

#### **1yr. Avg. (Inferred Sale Price)**

*   **Source**: Same as "List at".
*   **Logic**: This is the **mean of all inferred sale prices over the entire year**, after outlier rejection. It provides a more conservative, baseline valuation of the book compared to the peak "List at" price.

#### **All-in Cost**

*   **Source**: User settings and calculated fees.
*   **Function**: `business_calculations.py -> calculate_all_in_cost()`
*   **Logic**: `("Now" Price) + (Total AMZ Fees) + (Prep Fee) + (Est. Tax) + (Conditional Shipping)`
    *   It correctly applies the `estimated_shipping_per_book` cost from settings **only if** the `Shipping Included` flag for the deal is false.

#### **Min. List Price**

*   **Source**: "All-in Cost" and user settings.
*   **Function**: `business_calculations.py -> calculate_min_listing_price()`
*   **Logic**: `("All-in Cost") * (1 + Default Markup %)`
    *   This calculates the break-even listing price after accounting for the user's desired profit margin.

#### **Profit** & **Margin**

*   **Source**: "List at" and "All-in Cost".
*   **Function**: `business_calculations.py -> calculate_profit_and_margin()`
*   **Logic**: Standard profit (`"List at" - "All-in Cost"`) and margin (`Profit / "List at"`) calculations.

#### **Trend**

*   **Source**: Keepa API (historical "NEW" price data).
*   **Function**: `new_analytics.py -> get_trend()`
*   **Logic**:
    1.  The function looks at the history of the **"NEW" price**, not "USED".
    2.  It identifies the last 5 *unique* price changes, ignoring flat periods.
    3.  It compares the first and last price in this window to determine the short-term trend, returning '⇧' (up), '⇩' (down), or '-' (flat).

---

## Externalizing Keepa Deal Query

The hardcoded Keepa API query string in `keepa_api.py` defines the base criteria for all deals that enter the pipeline.

### Proposed Feature

*   **Goal**: Allow an administrator to change these deal-finding parameters without modifying the code.
*   **Implementation Idea**:
    1.  Create a simple form on a new, admin-only page (e.g., `/admin/settings`).
    2.  This page would have a `<textarea>` field where an admin can paste the JSON query copied directly from the Keepa Deals "Show API query" link.
    3.  On submit, the backend saves this JSON to a new file, e.g., `keepa_query.json`.
    4.  The `fetch_deals_for_deals` function in `keepa_api.py` will be modified to read this file. If the file exists, it uses the query from the file; otherwise, it falls back to the current hardcoded default.
*   **Benefit**: This provides flexibility to "cast a wider net" or target different types of deals without requiring a new code deployment. It also ensures the base query is not lost or accidentally modified during other development tasks.
