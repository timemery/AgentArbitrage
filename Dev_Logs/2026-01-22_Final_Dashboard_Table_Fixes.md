# Final Resolution: Dashboard Sticky Headers & Row Spacing (Spacer Row Strategy)

## Overview
This task resolved a persistent conflict between two critical UI requirements for the Dashboard table:
1.  **Sticky Headers:** A complex stack of 4 sticky elements (Filter Panel, Group Headers, Column Headers, Sort Arrows) that must remain flush and aligned during scroll.
2.  **Row Spacing:** A 10px visual gap between data rows to create a "pill" effect with rounded corners.

## The Challenge
The standard CSS property `border-spacing: 0 10px` on a `border-collapse: separate` table is the typical way to create gaps between rows. However, this property creates **physical gaps** in the table structure. 
*   **Impact on Sticky:** These structural gaps forced the sticky header rows apart, creating 10px "mystery margins" between the header sections where the background content would bleed through.
*   **Previous Failed Attempts:** 
    *   We attempted to patch this by adding `box-shadow` fillers to "plug" the gaps, but this was visually fragile.
    *   We attempted to adjust the `top` offsets to overlap the headers, but this caused alignment issues and didn't solve the structural underlying problem.

## The Solution: "Spacer Row" Injection
To solve this, we decoupled the structural requirements (Sticky) from the visual requirements (Row Gaps).

### 1. Structural Fix (CSS)
We removed the structural spacing entirely to support the sticky headers.
*   `#deals-table table { border-spacing: 0; }`
*   Header offsets were recalculated to be perfectly flush (e.g., Sort Arrows at 221px exactly touching the Column Headers at 190px + 31px height).

### 2. Visual Fix (JavaScript + CSS)
To restore the 10px gap between data rows without `border-spacing`, we implemented a **Spacer Row Injection** strategy.

**Logic:**
Inside the `renderTable` function in `dashboard.html`, immediately after generating a data row `<tr>`, we inject a spacer row:
```javascript
table += `<tr class="spacer-row"><td colspan="${columnsToShow.length}">&nbsp;</td></tr>`;
```

**Critical Implementation Detail (The "Collapse" Bug):**
Initial attempts failed because browsers often collapse empty table rows (`<td></td>`) to 0 height. We overcame this by:
1.  **Content:** Explicitly injecting a non-breaking space (`&nbsp;`) into the cell.
2.  **CSS Enforcement:**
    ```css
    .spacer-row td {
        height: 10px !important;
        line-height: 10px !important; /* Forces the line box to exactly 10px */
        font-size: 1px !important;   /* Prevents the &nbsp; font metrics from expanding the height */
        background-color: transparent !important;
        padding: 0 !important;
        border: none !important;
        pointer-events: none;        /* Prevents interference with clicks */
    }
    ```

## Outcome
*   **Headers:** Perfectly flush with no gaps.
*   **Rows:** Visually separated by exactly 10px.
*   **Filter Panel:** Visual integrity restored using a 3-layer CSS approach (Transparent Parent -> Opaque Blocker -> Visual Background) to handle rounded corners over scrolling content.

This pattern (Spacer Rows + `border-spacing: 0`) should be the standard for any future tables in this application requiring sticky headers + row gaps.
