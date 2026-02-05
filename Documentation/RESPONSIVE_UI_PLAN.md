# Responsive Dashboard Strategy

## Overview
This document outlines the technical strategy to reduce the Deals Dashboard maximum width to **1200px** and implement a robust responsive design that gracefully handles narrower resolutions. The approach relies on a combination of CSS Media Queries and lightweight JavaScript enhancements to enable targeted column manipulation.

## 1. Base Layout Updates (CSS)

The current fixed width of `1333px` will be replaced with a fluid `max-width` constraint.

-   **Target Elements:** `#deals-table`, `.filter-panel`, `#sticky-header-shadow-line`, `.dashboard-content-wrapper`.
-   **CSS Change:**
    ```css
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    ```
-   **Sticky Headers:** The sticky header logic in `#deals-table` will be verified to ensure it respects the fluid width. The `left` and `right` positions (if any) will need to be checked, though the current implementation relies mostly on `top` and standard flow.

## 2. JavaScript Refactoring (`renderTable`)

To allow CSS to specifically target and hide columns based on breakpoints, we must assign unique identifiers to every table cell. The current implementation relies partly on generic classes.

-   **Action:** Modify the `renderTable` function in `dashboard.html`.
-   **Logic:** Inside the column loop, automatically generate a CSS class based on the column's data key.
    -   Example: `ASIN` -> `col-asin`
    -   Example: `Seller_Quality_Score` -> `col-seller-trust`
    -   Example: `Detailed_Seasonality` -> `col-season`
-   **Benefit:** This decouples the "hiding" logic from the Javascript, allowing us to manage all responsiveness purely in CSS.

## 3. Responsive Breakpoints (The "Narrowing" Strategy)

We will implement 4 distinct states using CSS Media Queries.

### State 1: Fluid Narrowing (1200px - 1024px)
-   **Behavior:** The table shrinks naturally.
-   **Adjustments:**
    -   Reduce horizontal padding in table cells (`padding: 0 5px`).
    -   Slightly reduce font size if necessary (`11px`).
    -   Ensure `white-space: nowrap` doesn't force overflow (or allow controlled wrapping for headers).

### State 2: Remove Low-Priority Data (< 1024px)
-   **User Instruction:** "Eliminate the ASIN column".
-   **CSS:**
    ```css
    @media (max-width: 1024px) {
        .col-asin { display: none; }
    }
    ```

### State 3: Aggressive Truncation (< 900px)
-   **User Instruction:** "Title and Season columns... showing only 4 characters".
-   **CSS:**
    ```css
    @media (max-width: 900px) {
        .col-title span,
        .col-season span {
            max-width: 5ch; /* 4 chars + ellipsis space */
            text-overflow: ellipsis;
            overflow: hidden;
            display: inline-block;
            vertical-align: bottom;
        }
    }
    ```
-   **Note:** The existing "Hover to view full text" functionality will be preserved as it relies on the `title` attribute and absolute positioning of the span on hover, which works independently of the static width.

### State 4: Minimal View (< 768px)
-   **User Instruction:** "Eliminate the two Trust Rates columns".
-   **CSS:**
    ```css
    @media (max-width: 768px) {
        .col-seller-trust,
        .col-profit-confidence { display: none; }
    }
    ```

## 4. Filter Panel Responsiveness

The current Filter Panel is also fixed at `1333px`.

-   **Strategy:** Enable Flexbox Wrapping.
-   **CSS:**
    ```css
    .sliders-wrapper {
        flex-wrap: wrap;
        gap: 10px; /* Reduce gap on smaller screens */
        justify-content: center;
    }
    ```
-   **Height Adjustment:** The "Open" state height (`102px`) might need to be dynamic (`auto`) or increased to accommodate wrapped rows on very narrow screens.

## 5. Implementation Task List

1.  **Modify `templates/dashboard.html`**: Update JS to inject column classes.
2.  **Modify `static/global.css`**:
    -   Update width constraints (1333px -> 1200px).
    -   Add Media Queries for the 3 breakpoints.
    -   Add styles for `.sliders-wrapper` wrapping.
3.  **Verification**: Test resizing the window to ensure columns disappear/shrink as expected and the UI remains broken-free.
