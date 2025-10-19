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

*   **Source**: Inferred sale dates, product metadata, and AI reasoning.
*   **Function**: `seasonality_classifier.py -> classify_seasonality()`
*   **Logic (Pre-DB logic to be restored)**:
    1.  **Date-Driven Analysis**: The system first analyzes the dates of the inferred peak and trough sale prices (from the "List at" calculation) to identify which months consistently have the highest sale prices.
    2.  **Metadata Enrichment**: This date-based finding is combined with the book's metadata (Title, Genre).
    3.  **AI Refinement**: The combined data (e.g., "Peak sales in Jan/Feb" + "Genre: Textbooks") is passed to an XAI model to derive a final, human-readable season (e.g., "Textbook Season"). The AI is always used to ensure maximum accuracy.
    4.  **Default**: If no clear pattern emerges, it defaults to "Year-round".

#### **Sells**

*   **Source**: The output of the "Season" column.
*   **Function**: `seasonality_classifier.py -> get_sells_period()`
*   **Logic (Pre-DB logic to be restored)**:
    1.  This function acts as a simple mapping. It takes the season name (e.g., "Tax Season") and returns a human-readable date range (e.g., "Feb - Apr").
    2.  For "Year-round" books, it returns "All Year".

---

### **Seller Details**

#### **Name (Seller Name)**

*   **Source**: Keepa API (`product['offers']` -> seller data).
*   **Logic**: This logic identifies the seller of the "Best Price" offer. The column header in the UI should be "Name", while the group header is "Seller Details".
*   **Notes**: UI truncates to 120px.

#### **Seller Score**

*   **Source**: Keepa API (seller rating and review count).
*   **Logic**: A quality score is calculated based on the seller's feedback rating and the total number of ratings. A "New Seller" is one with no rating history.

---

### **Deal Details & Current Best Price**

#### **Now (Current Price)**

*   **Source**: Keepa API (`product['offers']`).
*   **Logic (Pre-DB logic to be restored)**:
    1.  This represents the **lowest currently available USED price**.
    2.  There should never be a `"-"` in this column for a deal found by the Keepa API. The logic must be robust enough to always find a price. Seller filtering should not be used here; instead, the "Seller Score" column informs the user.

#### **Condition**

*   **Source**: Keepa API (`product['offers']`).
*   **Logic**: Displays the condition of the offer that corresponds to the "Now" price.

---

### **Profit Estimates & Recommended Listing Price**

#### **List at (Peak Inferred Sale Price)**

*   **Source**: Keepa API (historical price and sales rank data).
*   **Function**: `stable_calculations.py -> infer_sale_events()` and related analytics.
*   **Logic (Pre-DB logic to be restored)**:
    1.  **Infer Sale Events**: Analyzes 2 years of historical data for patterns indicating a sale (offer count drop + sales rank drop).
    2.  **Outlier Rejection**: Uses a symmetrical Interquartile Range (IQR) to discard anomalously high and low inferred sale prices.
    3.  **Peak/Trough Analysis**: Groups cleaned sale prices by month to find peak/trough seasons.
    4.  **Statistical Calculation**: The **mode** (most frequently occurring price) of the inferred sale prices during the peak season is calculated.
    5.  **AI Verification**: The result is passed to an XAI model for a final reasonableness check (e.g., "For a Christmas book, is a peak price of $50 reasonable?").
    6.  **Final Value**: This gives the user an ambitious but highly accurate target listing price.

#### **1yr. Avg. (Inferred Sale Price)**

*   **Source**: Same as "List at".
*   **Logic**: This is the **mean of all inferred sale prices over the entire year**, after outlier rejection. It provides a more conservative, baseline valuation.

#### **All-in Cost**

*   **Source**: User settings and calculated fees.
*   **Function**: `business_calculations.py -> calculate_all_in_cost()`
*   **Logic**: `("Now" Price) + (FBA Pick&Pack Fee) + (Referral Fee) + (Prep Fee) + (Est. Tax) + (Conditional Shipping)`
    *   **Referral Fee Calculation**: The `Referral Fee` is a percentage taken from the final sale price. For this calculation, it should be: `("List at" Price) * (Referral Fee %)`.
    *   **Conditional Shipping**: The `estimated_shipping_per_book` cost is added **only if** the `Shipping Included` flag is false.

#### **Min. List Price**

*   **Source**: "All-in Cost" and user settings.
*   **Function**: `business_calculations.py -> calculate_min_listing_price()`
*   **Logic**: `("All-in Cost") / (1 - Default Markup %)`
    *   This calculates the listing price required to achieve the user's desired profit margin. It is not a "break-even" price. It is used in repricing software as the floor price to prevent selling for too low a profit.

#### **Profit** & **Margin**

*   **Source**: "List at" and "All-in Cost".
*   **Function**: `business_calculations.py -> calculate_profit_and_margin()`
*   **Logic**: Standard profit (`"List at" - "All-in Cost"`) and margin (`Profit / "List at"`) calculations.

#### **Trend**

*   **Source**: Keepa API (historical "NEW" and "USED" price data).
*   **Function**: `new_analytics.py -> get_trend()`
*   **Logic (to be implemented)**:
    1.  **Combined Data**: The function should look at both "NEW" and "USED" price histories.
    2.  **Dynamic Sample Size**: The number of unique price changes to analyze should be based on the book's 365-day average sales rank:
        *   **High Velocity (Rank < 100k):** Use a larger sample (e.g., 10-15 changes).
        *   **Medium Velocity (Rank 100k-500k):** Use a medium sample (e.g., 5 changes).
        *   **Low Velocity (Rank > 500k):** Use a smaller sample (e.g., 3 changes).
    3.  **Final Value**: Compares the first and last price in the dynamic window to return '⇧' (up), '⇩' (down), or '-' (flat). This should minimize flat results.
