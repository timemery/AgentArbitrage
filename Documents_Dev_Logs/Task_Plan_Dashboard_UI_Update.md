# Task Plan: Dashboard UI Overhaul (Safe Parallel Dev)

**Objective:** Implement the "Supply & Demand" focused dashboard design using a parallel test file (`dashboard_test.html`) to ensure zero disruption to the live application.

## 1. Safety & Isolation Strategy
*   **Parallel File:** Create `templates/dashboard_test.html` (copy of `dashboard.html`).
*   **Test Route:** Add `/dashboard-test` route in `wsgi_handler.py` accessible only to admins (or dev environment).
*   **No Database Reset:** Changes will rely on existing data where possible. New fields (`Drops`, `Offer Trend`) will be implemented in the UI but may show placeholder/fallback data until the Updater naturally populates them over time.

## 2. UI Implementation (`dashboard_test.html`)

### Group 1: Book Details
*   **Columns:** ASIN, Title, Condition.
*   **Changes:**
    *   **Condition:** Use existing "U - Very Good" string (backend mapping already applied).
    *   **Removed:** Genre, Binding (Verify "Binding" removal, user said "Removed" in spec).

### Group 2: Supply & Demand (New)
*   **Rank:**
    *   **Formatter:** JS function `formatRank(num)` -> "4.5M", "150k".
    *   *Source:* `Sales_Rank_Current`.
*   **Drops:**
    *   **Data:** `Sales_Rank_Drops_last_30_days`.
    *   *Note:* If missing, display "-".
*   **Offers:**
    *   **Data:** `Used_Offer_Count_Current` + Trend.
    *   *Logic:* Compare `Used_Offer_Count_Current` vs `Used_Offer_Count_365_days_avg` (as 30d avg is missing).
    *   *Visual:* "12 ↘" (Green if falling, Red if rising).
*   **Season:** `Detailed_Seasonality` (No change).

### Group 3: Deal Details (Renamed)
*   **1yr Avg:**
    *   **Source:** `Recent_Inferred_Sale_Price` (or `1yr_Avg` if explicitly populated).
    *   *Note:* User identified this as "yearly average inferred sale price" (not Rank).
*   **Now:** `Best_Price` (or `Price_Now`).
*   **% ⇩:**
    *   **Source:** `Percent_Down`.
    *   *Note:* Represents percent below current "best" price from inferred sale price.
*   **Ago:**
    *   **Header:** Rename "Changed" -> "Ago".
    *   **Logic:** Keep existing `formatTimeAgo` + `Trend` arrow.
*   **AMZ:**
    *   **New Column.**
    *   **Logic:** `if (deal.Amazon_Current > 0) return '⚠️'; else return '';`
*   **Gated:** Existing logic.

### Group 4: Trust Ratings
*   **Seller:** `Seller_Quality_Score`.
    *   **Format:** "8 / 10" (No change to logic/scaling per user instruction).
*   **Estimate:** `Profit_Confidence`.
    *   **Format:** "64%".

### Group 5: Profit Estimates
*   **All in:** `All_in_Cost`.
*   **Profit:** `Profit`.
*   **Margin:** `Margin`.
*   **Buy >:**
    *   **Move:** Move "Buy" button from "Actions" group to here.
    *   **Style:** Orange button, text "Buy >".

## 3. Backend Support (`wsgi_handler.py`)
1.  **Route:** Add `@app.route('/dashboard-test')`.
2.  **API:** Ensure `api_deals` returns `Sales_Rank_Drops_last_30_days`, `Amazon_Current`, `Used_Offer_Count_Current`, `Used_Offer_Count_365_days_avg`, `Recent_Inferred_Sale_Price`.

## 4. Verification Steps
1.  Access `/dashboard-test`.
2.  Verify column order and grouping match Excel spec exactly.
3.  Verify "Rank" is condensed (e.g., 4.5M).
4.  Verify "AMZ" warning appears for Amazon listings.
5.  Verify "Buy >" button position.
6.  Verify "Ago" column has trend arrow + time.
