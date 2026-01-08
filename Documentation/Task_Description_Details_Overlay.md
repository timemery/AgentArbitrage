# Task Description: Redesign Deal Details Overlay

## Overview
The objective of this task is to completely redesign the "Deal Details" overlay in the dashboard (`templates/dashboard.html`) to match the provided concept image (`image.png`). The new design replaces the tabbed interface with a high-density, 4-column grid layout that consolidates all critical decision-making data into a single view.

## 1. Visual & Layout Requirements (Frontend)
Refer to `image.png` for the visual reference.

### General Layout
- **Remove Header:** The standard modal header (containing Title and ASIN) must be **removed**. This information is now integrated into the table below.
- **"Advice from Ava" Section:**
  - Positioned at the very top of the overlay, *above* the data table.
  - Styled to match the data cells (light background, border).
  - **Content:** Displays the AI-generated advice text.
  - **Style:** "Advice from Ava" label in bold, followed by the text.
- **Action Bar (Top Right):**
  - **Gated Status:** Display a checkmark (✔) or "Gated" status next to the buttons.
  - **Buy Now Button:** A button styled similarly to the dashboard "Reset" button.

### Data Grid Structure
The main content is a 4-column grid. Use a CSS Grid or Table layout to achieve alignment.

#### Group 1: Book Details
*   **Header:** "Book Details"
*   **Rows:**
    *   **ASIN**: Display ASIN.
    *   **Title**: Truncate with ellipsis. **Hover:** Show full title.
    *   **Genre**: Display `Categories - Sub`. Truncate with ellipsis. **Hover:** Show full text.
    *   **Binding**: Display `Binding`.
    *   **Condition**: Display `Condition` (e.g., "U - Like New").
    *   **Publisher**: Display `Manufacturer`. Truncate with ellipsis. **Hover:** Show full text.
    *   **Published**: Display `Publication Date`.
    *   *(Separator / Sub-header)*: **Seller Details**
    *   **Name**: Display `Seller`. Truncate with ellipsis. **Hover:** Show full text.
    *   **Trust**: Display `Seller_Quality_Score` as "X / 10" (e.g., "10 / 10").

#### Group 2: Sales Rank (Supply & Demand)
*   **Header:** "Sales Rank"
*   **Rows:**
    *   **Current**: `Sales Rank - Current` (Format: "4.5 M" or "289 k").
    *   **180 Days Avg**: `Sales Rank - 180 days avg.`
    *   **365 Days Avg**: `Sales Rank - 365 days avg.`
    *   *(Separator / Sub-header)*: **Rank Drops**
    *   **Last 180 Days**: `Sales Rank - Drops last 180 days`.
    *   **Last 365 Days**: `Sales Rank - Drops last 365 days`.
    *   *(Separator / Sub-header)*: **Used Offer Counts**
    *   **Current**: `Used Offer Count - Current` + Trend Arrow (e.g., "1 ↗").
    *   **Last 180 Days**: `Used Offer Count - 180 days avg.` + Trend Arrow.
    *   **Last 365 Days**: `Used Offer Count - 365 days avg.` + Trend Arrow.

#### Group 3: Deal & Price Benchmarks
*   **Header:** "Deal & Price Benchmarks"
*   **Rows:**
    *   **Now**: `Price Now` (Best Price).
    *   **Shipping Included**: "Yes" or "No" (based on `Shipping Included` field).
    *   **1yr Avg**: `1yr. Avg.` price.
    *   **% ⇩ Avg**: `% Down` (Percent discount vs 1yr Avg).
    *   **Price Trending**: Directional Arrow (e.g., ↘) from `Trend` column.
    *   **Updated**: Time since `last_price_change` (e.g., "17 hrs").
    *   **Amazon - Current**: `Amazon - Current` price.
    *   **Amazon - 1yr Avg**: `Amazon - 365 days avg.` price.
    *   **Buy Box Used - Current**: `Buy Box Used - Current` price.
    *   **Buy Box Used - 1yr Avg**: `Buy Box Used - 365 days avg.` price.

#### Group 4: Listing & Profit Estimates
*   **Header:** "Listing & Profit Estimates"
*   **Rows:**
    *   **Estimate Trust**: `Profit Confidence` (e.g., "80%").
    *   **Profit**: `Profit` value.
    *   **Margin**: `Margin` value.
    *   **Max. List at**: `List at` price.
    *   **Min. List at**: `Min. Listing Price`.
    *   *(Separator / Sub-header)*: **Seasonality**
    *   **Selling Season**: `Detailed_Seasonality` (e.g., "Law School").
    *   **Est. Sell Date**: `Sells` column (e.g., "Nov - Jan").
    *   **Est. Buy Date**: **NEW FIELD** (See Backend Requirements).
    *   **Est. Buy Price**: `Expected Trough Price`.

### Styling Notes
*   **Truncation:** Title, Genre, Publisher, and Seller Name must have a fixed max-width (approx 110px) and use `text-overflow: ellipsis`.
*   **Hover:** Full text must appear on hover for truncated fields.
*   **Formatting:** Follow the specific currency ($) and number formats (k/M) shown in the image.

## 2. Backend & Data Requirements
To support the new layout, the following backend updates are required:

### A. Seasonality Logic (`keepa_deals/seasonality_classifier.py`)
1.  **Implement `get_buy_period(detailed_season)`:**
    *   Create a function that returns the "Best Buy Date" (off-season) corresponding to each `detailed_season`.
    *   *Logic:* Roughly 3-6 months prior to the `get_sells_period` start, or the seasonal trough.
    *   *Map:*
        *   "Textbook (Summer)" -> "Apr - May"
        *   "Textbook (Winter)" -> "Nov - Dec"
        *   "Law School" -> "Jun - Jul"
        *   (Define logical buy periods for all keys in `SEASON_CLASSIFICATIONS`).
2.  **Expose Data:** Ensure this value is calculated during processing and stored/returned for the frontend (either in a new DB column or computed on the fly in the API response).

### B. Data Availability (`keepa_deals/processing.py` / `stable_products.py`)
1.  **Verify/Add Columns:** Ensure the following fields are accurately calculated and populated in the database:
    *   `Sales Rank - Drops last 180 days`
    *   `Sales Rank - Drops last 365 days`
    *   `Used Offer Count - 180 days avg.`
    *   `Used Offer Count - 365 days avg.`
2.  **Trend Calculation:** Ensure trend arrows (↗, ↘, →) can be derived for the 180-day and 365-day Offer Counts (comparing them to... potentially the current count or a longer/shorter average). *Clarification:* If no historical trend data exists for these specific windows, display the value only or a logical comparison vs Current.

## 3. Implementation Steps
1.  **Backend:** Update `seasonality_classifier.py` with `get_buy_period`.
2.  **Backend:** Verify `180 days` metrics in `processing.py`.
3.  **Frontend:** Edit `dashboard.html`.
    *   Locate the "Details" modal/overlay code.
    *   Replace the existing HTML structure with the new 4-column grid.
    *   Update the JavaScript that populates the modal (`openDealDetails` or similar) to map the new JSON fields to the new HTML elements.
    *   Apply CSS for the grid layout, truncation, and "Advice" positioning.
4.  **Verification:**
    *   Load the dashboard.
    *   Click a deal to open the overlay.
    *   Verify all 4 columns are populated.
    *   Verify hover tooltips on Title/Genre/Publisher.
    *   Verify "Advice from Ava" is at the top.
