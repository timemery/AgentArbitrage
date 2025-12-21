# Dashboard Specification

This document serves as the **Single Source of Truth** for the dashboard's visual presentation. It defines the exact columns, their data sources, formatting rules, and display order.

**Goal:** Separate the *view* logic (this doc) from the *model* logic (`data_logic.md`) to prevent regressions in how data is presented to the user.

---

## Column Specification

The columns below are listed in the **exact order** they must appear on the dashboard (from left to right).

### 1. Book Details Group

| Header | Data Source (DB Column) | Formatting / Transformation Rules |
| :--- | :--- | :--- |
| **ASIN** | `ASIN` | Displayed as plain text. Clicking the row opens the detail overlay. |
| **Title** | `Title` | Truncated via CSS (ellipsis) if too long. Full title available on hover/tooltip. |
| **Genre** | `Categories_Sub` | If value starts with "Subjects", that prefix is removed. If empty or "-", displays "No Subject Listed". |
| **Binding** | `Binding` | **Abbreviated:**<br>- Audio CD -> **CD**<br>- Board book -> **BB**<br>- Hardcover -> **HC**<br>- Paperback -> **PB**<br>- Mass Market Paperback -> **MMP** |
| **Condition** | `Condition` | **CRITICAL: Must be Abbreviated**<br>- New -> **N**<br>- Used - Like New -> **U - LN**<br>- Used - Very Good -> **U - VG**<br>- Used - Good -> **U - G**<br>- Used - Acceptable -> **U - A**<br>*(Note: Raw DB values are numeric strings "1"-"5" or full strings. They must be mapped to these codes.)* |

### 2. Sales Rank & Seasonality Group

| Header | Data Source (DB Column) | Formatting / Transformation Rules |
| :--- | :--- | :--- |
| **Current** | `Sales_Rank_Current` | Formatted with commas (e.g., `57,828`). |
| **1yr. Avg** | `Sales_Rank_365_days_avg` | Formatted with commas (e.g., `45,200`). |
| **Season** | `Detailed_Seasonality` | Plain text (e.g., "High School", "Year-round"). |
| **Sells** | `Sells` | Plain text (e.g., "Aug - Sep"). |

### 3. Seller Details Group

| Header | Data Source (DB Column) | Formatting / Transformation Rules |
| :--- | :--- | :--- |
| **Name** | `Seller` | Plain text. If "New Seller" or unknown, handled gracefully. |
| **Trust** | `Seller_Quality_Score` | **Score / 10** format.<br>- Value is stored as float 0-5.<br>- Display: `round(Value * 10)` followed by `/ 10`.<br>- Example: `4.9` becomes **49 / 10**.<br>- "New Seller" -> **Unrated**. |

### 4. Deal Details & Current Best Price Group

| Header | Data Source (DB Column) | Formatting / Transformation Rules |
| :--- | :--- | :--- |
| **Changed** | `last_price_change` | **Relative Time:**<br>- < 60 mins -> `X mins. ago`<br>- < 24 hrs -> `X hrs. ago`<br>- < 30 days -> `X days ago`<br>- < 12 mos -> `X mos. ago`<br>- > 1 yr -> `X yrs. ago` |
| **1yr. Avg.** | `1yr_Avg` | Currency format: `$76.77`. |
| **Now** | `Best_Price` | Currency format: `$25.00`. Clicking links to Amazon offer page. |
| **% ⇩** | `Percent_Down` | Percentage format: `35%`. |
| **Trend** | `Trend` | Visual Arrows:<br>- **⇧** (Up)<br>- **⇩** (Down)<br>- **⇨** (Flat) |

### 5. Profit Estimates & Recommended Listing Price Group

| Header | Data Source (DB Column) | Formatting / Transformation Rules |
| :--- | :--- | :--- |
| **All_in_Cost** | `All_in_Cost` | Currency format: `$12.50`. |
| **Min. List** | `Min_Listing_Price` | Currency format: `$35.00`. |
| **List at** | `List_at` | Currency format: `$75.00`. |
| **Profit** | `Profit` | Currency format: `$40.00`. |
| **Margin** | `Margin` | Percentage format: `53.33%`. |
| **Profit Trust** | `Profit_Confidence` | Percentage format: `85%`. |

### 6. Actions Group

| Header | Data Source (DB Column) | Formatting / Transformation Rules |
| :--- | :--- | :--- |
| **Gated** | `Gated` (joined from `user_restrictions`) | **Status Icons:**<br>- Restricted -> **Apply** (Link to Amazon approval)<br>- Not Restricted -> **✓** (Green checkmark)<br>- Pending -> **Spinner** icon |
| **Buy** | `Buy_Now` | **►** icon. Links to Amazon product page. |

---

## Technical Implementation Notes

*   **Endpoint:** `/api/deals` (`wsgi_handler.py`)
*   **Template:** `templates/dashboard.html`
*   **Column Naming Conflict:** The database uses single underscores (e.g., `Sales_Rank_Current`), but legacy parts of the frontend code may refer to them differently. The API endpoint handles this mapping.
*   **Abbreviation Logic:** The `Condition` and `Binding` abbreviations are applied in the `api_deals` function in `wsgi_handler.py` before the JSON is sent to the frontend.

### 7. Header Controls (Above Grid)

| Control | Functionality | Logic |
| :--- | :--- | :--- |
| **Refresh Deals** | Manually triggers the "Janitor" task. | - Link text is dynamic.<br>- Default: **⟳ Refresh Deals**.<br>- Notification: **⟳ [Diff] New Deals found - Refresh Now** (if server count > local count).<br>- Clicking triggers `POST /api/run-janitor`. |
| **Deal Count** | Displays total records. | - Polls `/api/deal-count` (unfiltered) every 60s.<br>- Used to calculate the [Diff] for the notification. |
