# Task Plan: Dashboard UI Overhaul (Supply & Demand Focus)

**Objective:** Redesign the Deals Dashboard (`templates/dashboard.html`) to reduce information overload and focus on "Supply & Demand" metrics, implementing the specific design agreed upon in the "Dashboard and Deal Detail Overlay advice" session.

## 1. Grid Layout & Column Changes

The dashboard grid should be reorganized into the following groups and columns.

### Group 1: Book Details (Yellow Header)
*   **ASIN:** Standard display. *Recommendation: Hyperlink this to Amazon Product Page to replace the removed "Actions" column.*
*   **Title:** Standard truncation (hover for full).
*   **Condition:** Keep existing "U - VG" style abbreviations.

### Group 2: Supply & Demand (New Header!)
*   **Rank:**
    *   **Format:** Condensed notation (e.g., "3.4M", "150k") instead of raw numbers ("3,494,423").
    *   *Implementation:* Requires a JS formatter in `dashboard.html`.
*   **Drops (30d):**
    *   **Data:** Need to expose "30-day Sales Rank Drops" to the frontend.
    *   *Check:* Verify if `sale_events` count is available in the API response or if a new field `drops_30d` needs to be added to `processing.py`/`new_analytics.py`.
*   **Offers:**
    *   **Format:** "Count + Trend Arrow" (e.g., "12 ↘" or "15 ↗").
    *   *Intricacy:* The strategies emphasize that *rising* offers are bad and *falling* offers are good.
    *   *Backend Work:* Verify if an "Offer Count Trend" is calculated. If not, implement logic in `keepa_deals/new_analytics.py` similar to the Price Trend logic, comparing current offer count to a moving average or previous value.
*   **Season:** Standard Seasonality text (e.g., "Textbook (Winter)").

### Group 3: Trust Ratings (Yellow Header)
*   **Seller:** "8 / 10" format.
*   **Estimate:** (Renamed from "Profit Confidence" / "Profit Trust").
    *   **Data:** `Profit_Confidence` field.
    *   **Label:** Display as "**Estimate**" in the header.

### Group 4: Deal Details (Yellow Header)
*   **1yr Avg:** Currency.
*   **Now:** Currency (`Price Now`).
*   **% ⇩:** Percent Down.
*   **Ago:**
    *   **Critical Detail:** Must include the **Price Trend Arrow**.
    *   **Format:** "Trend + Time" (e.g., "⇩ 4d", "⇧ 2h").
    *   *Note:* The trend arrow was previously in its own column; it must be merged here.
*   **AMZ:** (New Column)
    *   **Logic:** Listed vs. Not Listed.
    *   **Display:**
        *   If Amazon is on the listing: Display **Warning Icon (⚠️)** or similar alert.
        *   If Amazon is NOT on the listing: Leave **Blank** (or minimal dash).
        *   *Goal:* Management by exception.
*   **Gated:** Standard Check/X/Spinner icons.

### Group 5: Profit Estimates (Yellow Header)
*   **All in:** (Renamed from "All in Cost").
*   **Profit:** Currency (Green/Red).
*   **Margin:** Percentage.
*   **Action Button:**
    *   **Header:** Empty (No text).
    *   **Cell Content:** A button labeled **"Buy >"**.
    *   **Style:** Similar to the "Apply" button style (Orange/Action color).
    *   **Behavior:** Links to Amazon (or opens the Deal Overlay, based on user workflow preference—likely Overlay first for safety).

## 2. Technical Requirements

### Backend (`wsgi_handler.py` / `keepa_deals`)
1.  **Offer Trend:** Implement logic to calculate `Offer_Count_Trend` (Up/Down/Flat) if not present.
2.  **30d Drops:** Ensure the count of sales rank drops in the last 30 days is available in the API response.
3.  **Amazon Presence:** Ensure a boolean or flag for `is_amazon_selling` is available to drive the "AMZ" column icon.

### Frontend (`templates/dashboard.html`)
1.  **Header Removal:** Remove the old blue headers and replace with the new Yellow grouping headers as shown in the design.
2.  **Column Config:** Update `renderTable` to match the new column order and formatting rules (especially the "3.4M" rank and merged "Ago" column).
3.  **CSS:** Update `static/global.css` to support the new "Buy >" button and column widths.

## 3. Pre-flight Check
*   Verify that "Estimate" refers to *Profit Confidence* (the probability of the profit being real) and not a dollar value.
*   Confirm the logic for the "Offers" arrow (Up = Bad/More Competition, Down = Good/Less Competition) to consider color-coding if necessary (Red up / Green down?).
