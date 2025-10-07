# Technical Documentation: Inferred Price Calculation Logic

## 1. Overview

This document details the system used to calculate the **Peak Price**, **Trough Price**, and **1-Year Average Price** for a given product (ASIN). The entire system is predicated on the concept of an "inferred sale," which is a historical moment where data strongly suggests a transaction occurred, rather than just a price listing.

The primary logic is housed in two key files:

- `keepa_deals/stable_calculations.py`
- `keepa_deals/new_analytics.py`

The process can be broken down into three main stages:

1. Inferring Sale Events
2. Analyzing Sales for Seasonality (Peak/Trough)
3. Calculating the 1-Year Average

------

## 2. Stage 1: Inferring Sale Events

This is the foundational step and is handled by the `infer_sale_events(product)` function in `keepa_deals/stable_calculations.py`.

### a. The "Sale" Trigger and Confirmation

A sale is inferred by correlating two distinct events within a 72-hour window over the last two years of a product's history:

1. **The Trigger:** A drop in the offer count for either **New** or **Used** listings. The system processes `csv[11]` (New offers) and `csv[12]` (Used offers) from the Keepa product data. It uses `pandas.DataFrame.diff()` to detect negative changes in the offer count time series.
2. **The Confirmation:** A drop in the product's Sales Rank (`csv[3]`). A rank drop (e.g., from 100,000 to 80,000) is a strong indicator of a recent sale.

If a rank drop occurs within 72 hours *after* an offer count drop, the system flags it as a confirmed sale event.

### b. Price Association

When a sale is confirmed, the system associates a price with it. It uses `pandas.merge_asof` to find the nearest corresponding price from the `new_price_history` (`csv[1]`) or `used_price_history` (`csv[2]`) at the time of the sale event.

### c. Symmetrical Outlier Rejection

After collecting all inferred sale events from the last two years, the data is sanitized to remove statistical outliers. This is a critical step to prevent anomalous prices from skewing the results.

- The function calculates the first quartile (Q1) and third quartile (Q3) of all inferred sale prices.
- The Interquartile Range (IQR) is calculated (`IQR = Q3 - Q1`).
- A `lower_bound` (`Q1 - 1.5 * IQR`) and an `upper_bound` (`Q3 + 1.5 * IQR`) are established.
- Any sale with a price outside this range is discarded.

**Key Point:** This rejection is **symmetrical**, meaning it removes both unusually high and unusually low prices, leading to a more balanced and representative dataset of "sane" sales.

The function returns a list of these sanitized `sane_sales` events.

------

## 3. Stage 2: Seasonality Analysis (Peak & Trough)

This stage is handled by the `analyze_seasonality(product, sale_events)` function in `keepa_deals/stable_calculations.py`.

### a. Monthly Grouping

The function takes the list of sane sale events and groups them by calendar month. For each month, it calculates the `mean`, `median`, and `count` of sales.

**Note:** The function requires data from at least two different months to perform a meaningful analysis. If all sales occurred in the same month, it returns a default "Year-Round" result with no price data.

### b. Peak/Trough Calculation

The core logic for finding the peak and trough prices is as follows:

1. It identifies the "peak month" by finding the month with the **highest `mean` price**.
2. It identifies the "trough month" by finding the month with the **lowest `mean` price**.
3. The final **Peak Price** is the `mean` of all sales that occurred within that peak month.
4. The final **Trough Price** is the `mean` of all sales that occurred within that trough month.

**Key Point:** The system uses the `mean` (average) for the final price calculation, providing a traditional average of prices during the product's high and low seasons.

------

## 4. Stage 3: 1-Year Average Calculation

This final piece is handled by the `get_1yr_avg_sale_price(product)` function in `keepa_deals/new_analytics.py` to avoid circular dependencies.

### a. Data Filtering

This function also starts by calling `infer_sale_events` to get the list of sane sale events from the last two years. It then filters this list to include only sales that occurred within the **last 365 days**.

### b. Mean Calculation

If there are at least three sale events within the last year, the function calculates the **`mean`** of the `inferred_sale_price_cents` for those sales.

**Key Point:** Like the other calculations, this function uses the `mean`, not the `median`, for its final output, providing a true average sale price over the last year. If there are fewer than three sales, it returns a default `-` value.

---

### **How We FORMERLY Calculated Inferred Prices**

The entire system is built on the concept of an "inferred sale"—we find moments in a book's history that strongly suggest a sale occurred.

**1. Finding a "Sale"**

The system looks for two key signals happening close together over the last **two years**:

- **The Trigger:** The number of listed offers (either New or Used) drops. This suggests a copy was removed from the market.
- **The Confirmation:** Within **72 hours** after the offer drop, the book's Sales Rank also drops (meaning its rank number gets smaller). A rank drop is a very strong indicator that a sale happened.

If both of these events occur, the system records the listing price at that moment as a single "inferred sale price."

**2. Removing Outliers**

After gathering all the inferred sale prices from the last two years, the system does a statistical check to clean up the data. It identifies and **removes unusually high-priced sales**. The goal is to prevent a single, freakishly expensive sale from artificially inflating the averages.

**Important Note:** The current system only removes *high* outliers. It does **not** remove unusually low ones. This might be a key factor in why some averages appear low.

**3. Calculating the Final Numbers**

Once we have a clean list of inferred sale prices, the three numbers are calculated as follows:

- **Peak Price:** The system groups all sales by month. It finds the month with the highest *median* sale price and then takes the median of all sales in that "peak month." This represents the typical sale price during the book's busiest season over the last two years.
- **Trough Price:** This is the same as the Peak Price, but it uses the month with the *lowest* median sale price.
- **1yr. Avg.:** The system takes all the inferred sales from just the **last 365 days** and calculates the **median** of those prices. It only provides an answer if it finds at least three sales in that one-year period.

### **Suggestions for Improvement**

Based on my analysis and your concerns, here are a few ideas for how we could make these calculations even more accurate and transparent. We can implement any or all of these.

**Suggestion 1: Use Symmetrical Outlier Rejection (Addresses "Too Low" Averages)**

- **What:** Right now, we only trim off the unusually high sale prices. I suggest we also trim off the unusually *low* sale prices.
- **Why:** This would create a more balanced and realistic average. It would prevent the calculations from being skewed downwards by things like penny-books, clearance sales, or copies sold in "Acceptable" condition with missing pages, which might not be representative of a typical sale. This is my top recommendation to address the "negative profit" issue you're seeing.

**Suggestion 2: Use Mean Instead of Median**

- **What:** We are currently using the `median` for all calculations. The `median` is the "middle" value, which is excellent for ignoring outliers. However, since we are already doing a good job of removing outliers (and could do an even better job with Suggestion 1), we might get a more representative price by using the `mean` (the traditional average).
- **Why:** After cleaning the data, the `mean` might better reflect the book's true average sale price across all its transactions. The logs already show that the `mean` is being calculated alongside the `median`, so switching to it would be a straightforward change.

**Suggestion 3: Make the "1yr. Avg." Time Window Adjustable**

- **What:** You mentioned that Keepa uses a 180-day average. We could make the time window for our "1yr. Avg." calculation a configurable setting.
- **Why:** This would give you the flexibility to choose between a 90-day, 180-day, or 365-day average. A shorter window would be more responsive to recent price trends, while a longer window provides a more stable, long-term view.

Please let me know your thoughts on these ideas. I'm ready to move forward with whichever approach you think is best.

**My direction based on the last Agent's suggestions.** 

I like the first 2 suggestions, but not sure about the third. Unless perhaps that third choice is an interactive one in the header row, and would resort/refresh the results in that column as well as how it effects other columns down the line like List at (aka Peak sale price), and profit/margin and anything else that uses the List at (Peak) price as part of another calculation. Also, the fact that this is a 1 year average, covers the yearly seasonal fluctuations, where a shorter time frame would not. It is an interesting idea, and I will make a note of it for consideration later on, but let's implement just the first 2 ideas for now.  

**Agent's notes on changes made:**

feat: Improve accuracy of inferred price calculations

This commit improves the accuracy and realism of the inferred sale price calculations (Peak, Trough, and 1yr. Avg.) based on user feedback.

The key changes are:

1.  **Symmetrical Outlier Rejection:** The `infer_sale_events` function in `keepa_deals/stable_calculations.py` now removes both unusually high and unusually low sale prices from the data set before analysis. The previous method only removed high outliers, which could lead to averages being skewed downwards. This change ensures a more balanced and representative set of sale data.

2.  **Switch to Mean from Median:** The `analyze_seasonality` function (for Peak/Trough prices) and the `get_1yr_avg_sale_price` function have been updated to use the `mean` (standard average) instead of the `median`. After cleaning the data with symmetrical outlier rejection, the mean provides a more traditional and representative average of the likely sale prices.





















