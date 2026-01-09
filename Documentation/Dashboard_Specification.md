# Dashboard Specification

This document defines the visual layout, formatting, and behavior of the main Deals Dashboard. It acts as a contract between the backend data and the frontend presentation.

For the underlying data logic, please refer to **`Data_Logic.md`**.

---

## Grid Layout & Column Definitions

The dashboard uses a responsive grid layout. Columns are defined in `templates/dashboard.html`.

**Note:** Several columns (Genre, Binding, Name, Min. List, List at) have been removed from the visual dashboard as of Jan 2026, but their underlying logic and data extraction remain active in the backend for future use.

### 1. Main Data Grid

| Column Header | Data Field (Backend) | Visual Format / Behavior | Width | Sortable? |
| :--- | :--- | :--- | :--- | :--- |
| **Image** | `Image` | 60px height. Click expands to full size. | 70px | No |
| **Title** | `Title` | Truncated (2 lines). Hover shows full title. Hyperlink to Keepa. | Auto | No |
| **Condition** | `Condition` | **Abbreviated Map:** <br> `Used - Like New` -> **U - LN** <br> `Used - Very Good` -> **U - VG** <br> `Used - Good` -> **U - G** <br> `Used - Acceptable` -> **U - A** | 80px | Yes |
| **Rank** | `Sales_Rank_Current` | Integer with commas (e.g., "12,345"). | 90px | Yes |
| **Details** | `Detailed_Seasonality` | Text. | 110px | No |
| **S. Trust** | `Seller_Quality_Score` | **Scale 0-10:** Raw probability (0.0-1.0) * 10. Rounded to 1 decimal. | 80px | Yes |
| **Changed** | `last_price_change`, `Trend` | **Composite:** Trend Arrow + " " + Time Ago (e.g., "⇩ 2h ago"). <br> **Arrows:** ⇧ (Up), ⇩ (Down), ⇨ (Flat). | 100px | Yes |
| **Buy For** | `Best_Price` | Currency ($XX.XX). Bold font. | 90px | Yes |
| **Avg.** | `1yr_Avg` | Currency ($XX.XX). | 90px | Yes |
| **% ⇩** | `Percent_Down` | Percentage + "%". Bold if > 50%. | 70px | Yes |
| **P. Trust** | `Profit_Confidence` | Percentage + "%". | 80px | Yes |
| **Gated** | `is_restricted` (joined) | **Icons:** <br> ✅ (Green Check) = Allowed <br> ❌ (Red X) = Restricted (Click opens Approval URL) <br> ⏳ (Spinner) = Checking... <br> ⚠️ (Broken) = Error (Hover for details) | 60px | Yes |
| **Buy** | `Buy_Now` | Link to Amazon Product Page. | 60px | No |
| **Profit** | `Profit` | Currency ($XX.XX). **Color Coded:** <br> Green if > $0. <br> Red if < $0. | 90px | Yes |
| **Margin** | `Margin` | Percentage + "%". | 80px | Yes |

---

## Filtering Logic (Frontend & Backend)

The dashboard supports complex filtering via the side panel.

### Range Sliders (The "Any" Logic)
All sliders utilize a standardized "Any" state logic:
-   **Visual:** Setting a slider to **0** displays the label **"Any"**.
-   **Backend:** A value of `0` is excluded from the SQL query (treated as no filter), allowing NULLs and negatives to appear.
-   **Reset:** The "Reset" button explicitly sets all sliders to 0 and reloads the grid.

**Supported Filters:**
1.  **Min. Below Avg. (%)**: Filter by `Percent_Down`.
2.  **Min. Profit ($)**: Filter by `Profit`.
3.  **Min. Margin (%)**: Filter by `Margin`.
4.  **Max. Sales Rank**: Filter by `Sales_Rank_Current`.
5.  **Min. Profit Trust**: Filter by `Profit_Confidence`.
6.  **Min. Seller Trust**: Filter by `Seller_Quality_Score`.

### Special Filters
-   **Keyword Search:** (Commented out in HTML but supported in Backend via `keyword` param).
-   **Deal Count:** The badge in the header shows the total number of deals matching the *current* filters.

---

## Polling & Updates

1.  **Auto-Refresh:** The dashboard polls `/api/deal-count` every 30 seconds.
2.  **New Deal Notification:**
    -   Logic: Compares `local_record_count` (JS) vs `total_records` (API).
    -   Visual: "New Deals Available! Click to Refresh" banner appears if counts differ.
    -   **Context Aware:** The polling API call explicitly includes the *active filters* (e.g., `?margin_gte=10`) to ensure users are only notified about deals relevant to their current view.

---

## The "Janitor" & Data Freshness

To maintain a high-quality dashboard, the system implements a "Janitor" process.

-   **Trigger:** Runs automatically every 4 hours (Celery) or manually via "Refresh Deals" button.
-   **Action:** Deletes any deal from the database where `last_seen_utc` is older than **72 hours**.
-   **Impact on Dashboard:** Users may see the total deal count drop significantly after a refresh. This is expected behavior (garbage collection).
-   **User Feedback:** The "Refresh Deals" button triggers the Janitor *before* reloading the grid to ensure the user sees a clean state.

---

## Deal Details Overlay

The "Deal Details" overlay replaces the standard modal with a high-density, 4-column grid layout designed for rapid decision-making.

### 1. Layout & Structure
-   **Header:** The standard modal title is removed. Context is provided by the grid content.
-   **Ava Advice:** Positioned at the very top, spanning the full width, providing immediate AI analysis.
-   **Action Bar:** Top-right corner containing the "Gated" status and primary action button (Buy/Apply).

### 2. Data Grid (4 Columns)
The grid is divided into four logical groups:

#### Group 1: Book Details
-   **ASIN**: The product identifier.
-   **Title**: Truncated with ellipsis (Hover for full).
-   **Genre**: `Categories - Sub` (Truncated).
-   **Binding**: e.g., "Paperback".
-   **Condition**: e.g., "U - Like New".
-   **Publisher**: Manufacturer name.
-   **Published**: Publication Date.
-   **Seller Name**: Winning seller's name.
-   **Seller Trust**: Quality Score (X / 10).

#### Group 2: Sales Rank (Supply & Demand)
-   **Current**: Current Sales Rank.
-   **180 Days Avg**: Average rank over 6 months.
-   **365 Days Avg**: Average rank over 1 year.
-   **Rank Drops**:
    -   **Last 180 Days**: Count of drops.
    -   **Last 365 Days**: Count of drops.
-   **Used Offer Counts**:
    -   **Current**: Count + Trend Arrow (e.g., "15 ↘").
    -   **Last 180 Days**: Avg Count + Trend Arrow.
    -   **Last 365 Days**: Avg Count + Trend Arrow.

#### Group 3: Deal & Price Benchmarks
-   **Now**: `Price Now` (Best Price).
-   **Shipping Included**: Yes/No.
-   **1yr Avg**: Inferred average sale price.
-   **% ⇩ Avg**: Discount percentage relative to 1yr Avg.
-   **Price Trending**: Directional arrow.
-   **Updated**: Time since last price change.
-   **Amazon / Buy Box**:
    -   **Amazon - Current**: Amazon New Price (if available).
    -   **Amazon - 1yr Avg**: Long-term Amazon price.
    -   **Buy Box Used - Current**: Current Buy Box price.
    -   **Buy Box Used - 1yr Avg**: Long-term Buy Box price.

#### Group 4: Listing & Profit Estimates
-   **Estimate Trust**: `Profit Confidence` %.
-   **Profit**: Calculated Profit ($).
-   **Margin**: Calculated Margin (%).
-   **Max. List at**: The calculated "List at" (Peak) price.
-   **Min. List at**: The calculated floor price based on costs.
-   **Seasonality**:
    -   **Selling Season**: AI classification (e.g., "Fall Semester").
    -   **Est. Sell Date**: Predicted peak sales period.
    -   **Est. Buy Date**: Predicted trough month.
    -   **Est. Buy Price**: `Expected Trough Price`.

### 3. Action Bar Logic
The action bar adapts based on the user's restriction status:

-   **Restricted:**
    -   **Message:** "You are **Not Approved** to sell this title" (Red text).
    -   **Button:** "Apply Now" (Orange, links to Seller Central approval page).
-   **Approved:**
    -   **Message:** "You are **Approved** to sell this title" (White text).
    -   **Button:** "Buy Now" (Orange, links to Amazon product page).
-   **Pending:** Shows a spinner while checking status.
-   **Error:** Shows a warning icon if the API check failed.

---

## CSS & Styling Standards

-   **Color Palette:**
    -   Primary Blue: `#336699` (Headers, Active States)
    -   Filter Active: `rgba(102, 153, 204, 0.9)`
    -   Profit Green: `#28a745`
    -   Loss Red: `#dc3545`
-   **Latency:**
    -   Hover effects on navigation must be **instant**.
    -   CSS transitions on `background-color` are explicitly **disabled**.
-   **Header:** `<h1>` tags are explicitly removed from the main layout to maximize vertical screen real estate. Context is provided by the active navigation tab.
