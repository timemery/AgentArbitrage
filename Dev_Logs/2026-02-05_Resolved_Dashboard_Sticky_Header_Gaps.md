# Resolved Dashboard Sticky Header Gaps and Alignment

## Overview
Addressed visual regressions in the Deals Dashboard where "mystery gaps" appeared between sticky header rows (Group, Column, Sort Arrows) and above the Group Header. These gaps broke the solid, continuous appearance of the header stack and allowed content to bleed through during scrolling.

## Challenges
- **Sticky Positioning vs. Table Borders:** The `border-spacing: 0 10px` property on the table (needed for the "pill" look of data rows) created intrinsic gaps that also affected the header rows.
- **Top Offset Calculation:** The previous `top` offsets for the sticky headers included these 10px gaps, intentionally separating the headers.
- **Dynamic Interaction:** The issue was most visible during scrolling, where the background content would peek through the 10px transparent gaps between the sticky headers.

## Solution
1.  **Tightened Sticky Offsets:** Recalculated the `top` offsets for all sticky header layers to remove the gaps and make them sit flush against each other.
    -   **Group Header:** Reduced `top` from `+124px` to `+114px` (moved up 10px) to cover the top `border-spacing` gap.
    -   **Column Header:** Reduced `top` from `+190px` to `+170px` to sit flush with the Group Header (114px + 56px height = 170px).
    -   **Sort Arrows:** Reduced `top` from `+231px` to `+201px` to sit flush with the Column Header (170px + 31px height = 201px).
    -   **Shadow Line:** Adjusted `top` to `+236px` to maintain correct positioning relative to the stack.

2.  **Verification:**
    -   Created a Playwright script `verification/verify_dashboard.py` to automate the login and dashboard scrolling process.
    -   Generated a screenshot `verification/dashboard_sticky_headers.png` confirming the headers now stack perfectly without gaps.

## Technical Details
-   **File(s) Modified:** `static/global.css`
-   **Key CSS Change:** Updated `top: calc(var(--filter-panel-height) + Xpx)` values for `.group-header th`, `.column-header-row th`, `.sort-arrows-row td`, and `#sticky-header-shadow-line`.
