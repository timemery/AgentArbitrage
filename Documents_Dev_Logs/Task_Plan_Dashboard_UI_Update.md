# Task Plan: Dashboard UI Overhaul (Supply & Demand Focus)

**Objective:** Redesign the Deals Dashboard (`templates/dashboard.html`) to reduce information overload and focus on "Supply & Demand" metrics, strictly adhering to the user-provided Excel specification (image.png).

## 1. Grid Layout & Column Changes

The dashboard grid must be reorganized into the following groups and columns. Columns marked with "x Removed" in the spec must be deleted.

### Group 1: Book Details
*   **ASIN:** Standard display.
*   **Title:** Standard truncation.
*   **Condition:**
    *   **Rename:** Rename column header to **Condition**.
    *   **Data Transformation:** Map raw string codes to abbreviations:
        *   "Used - Very Good" -> "**U - Very Good**" (was "UG", now explicitly full word) - *Correction:* User spec says "U - Very Good", "U - Good", "U - Like New", "U - Acceptable".
        *   Wait, spec says: "U - Very Good", "C - Like New" etc.
        *   *Spec Note:* "modify Condition Labels: - New (no change), - U - Like New, - U - Very Good, ... - C - Like New...".
        *   *Implementation:* Update `api_deals` in `wsgi_handler.py` (or frontend JS) to apply this mapping.

### Group 2: Supply & Demand (New Header)
*   **Rank:**
    *   **Format:** Condensed notation (e.g., "**4.5M**", "120k").
    *   *Implementation:* JavaScript formatter.
*   **Drops:**
    *   **Data:** **New Field.** "30-day Sales Rank Drops".
    *   *Source:* `Sales_Rank___Drops_last_30_days` (sanitized DB column).
    *   *Display:* Raw integer (e.g., "15").
*   **Offers:**
    *   **Data:** **New Field.** "Count + Trend Arrow".
    *   *Source:* `Used Offer Count - Current`.
    *   *Trend Logic:* Compare `Used Offer Count - Current` vs `Used Offer Count - 30 days avg.` (derived from `keepa_deals/new_analytics.py` logic or calculated in SQL/Python).
    *   *Formatting:* "12 ↘".
    *   *Color Coding:*
        *   **Rising (Current > Avg):** Red (Bad).
        *   **Falling (Current < Avg):** Green (Good).
*   **Season:** No change.

### Group 3: Deal Details (Renamed/Reorganized)
*   **1yr Avg:** (Price). No change.
*   **Now:** (Price). No change.
*   **% ⇩:** No change.
*   **Ago:**
    *   **Format:** "Trend Arrow + Time" (e.g., "⇧ 4d").
    *   *Change:* Ensure Trend Arrow is part of this cell, not separate.
*   **AMZ:**
    *   **Data:** **New Field.** "Amazon Presence".
    *   *Source:* Check `Amazon - Current` (DB column `Amazon___Current`).
    *   *Logic:* If `Amazon - Current` > 0 (and not -1/None), display Warning Icon (⚠️). Else Blank.
*   **Gated:** Standard Check/Spinner.

### Group 4: Trust Ratings
*   **Seller:** (Renamed from "Trust"? No, "Seller Details" -> "Trust Ratings").
    *   **Data:** `Seller_Quality_Score`.
    *   **Format:** "**8 / 10**". (Likely needs scaling from 0-1 or 0-100).
*   **Estimate:** (Renamed from "Profit Confidence").
    *   **Data:** `Profit Confidence`.
    *   **Format:** Percentage (e.g., "**64%**").

### Group 5: Profit Estimates
*   **All in:** No change.
*   **Profit:** No change.
*   **Margin:** No change.
*   **Buy >:** (Replaces "Actions").
    *   **Content:** Button labeled "**Buy >**".
    *   **Style:** Orange/Action color (similar to "Apply").
    *   **Link:** `https://www.amazon.com/dp/{ASIN}`.

## 2. Technical Implementation Steps

### Backend (`wsgi_handler.py` / `keepa_deals`)
1.  **API Response (`/api/deals`):**
    *   Ensure `Sales_Rank___Drops_last_30_days` is included in the JSON response.
    *   Ensure `Used Offer Count - 30 days avg.` is included (for trend calculation) OR calculate `offer_trend` serverside and send as a field. *Recommendation:* Send `offer_trend` (-1, 0, 1) to simplify frontend logic.
    *   Ensure `Amazon___Current` is included.
    *   **Condition Mapping:** Implement the "U - Very Good" mapping logic in `api_deals` so the frontend receives the clean string, OR send raw string and map in JS. *Decision:* Map in Python `api_deals` using `condition_string_map`.

### Frontend (`templates/dashboard.html`)
1.  **Grid Reconfiguration:**
    *   Rewrite the `<thead>` to match the 5 Groups structure.
    *   Update `columns` definition in the DataTables/Grid initialization.
2.  **Formatters:**
    *   **Rank:** Write `formatRank(number)` function (e.g., `num / 1000000 + 'M'`).
    *   **Offers:** Write `formatOffers(count, trend)` function (Arrow logic + Color class).
    *   **Ago:** Combine `last_price_change` (Trend) and `last_update` (Time).
    *   **AMZ:** logic: `if (row.amz_price > 0) return '⚠️'; else return '';`
    *   **Buy Button:** Render `<a href="..." class="btn-buy">Buy ></a>`.
3.  **CSS:**
    *   Add `.btn-buy` style (Orange, compact).
    *   Adjust column widths to fit new layout.

## 3. Data Notes & Logic Verification
*   **Condition Mapping:**
    *   "Used - Like New" -> "U - Like New"
    *   "Used - Very Good" -> "U - Very Good"
    *   "Used - Good" -> "U - Good"
    *   "Used - Acceptable" -> "U - Acceptable"
    *   "Collectible - Like New" -> "C - Like New" (etc.)
    *   *Fallback:* If pattern is "Condition - Subcondition", map to "C - Subcondition" (first letter).
*   **Trend Logic:**
    *   **Price Trend:** (Existing) Rising = Green (Good for selling?), Falling = Red? *Wait*, usually Price Rising is Good for value, but "Trend" arrow usually indicates *change*.
    *   **Offer Trend:** (New) Rising = Red (Bad competition), Falling = Green (Good competition). **Crucial distinction.**

## 4. Verification Plan
*   Load Dashboard.
*   Verify all Removed columns are gone.
*   Verify "Supply & Demand" group exists.
*   Check "Rank" formatting (e.g., 4.5M).
*   Check "Offers" arrow colors (Find an item with rising offers -> Red).
*   Check "AMZ" warning (Find an item with Amazon price -> Warning).
*   Check "Condition" strings ("U - Very Good").
