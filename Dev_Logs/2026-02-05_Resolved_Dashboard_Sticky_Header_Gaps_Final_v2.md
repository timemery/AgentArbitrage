# Resolved: Dashboard Sticky Header Gaps & Filter Panel Corners (v2)

## Overview
Refined the dashboard sticky header implementation to address two specific user feedback items:
1.  **Extra Padding around Sort Arrows:** The user noted 10px "padding" above and 9px below the Sort Arrow row. This was caused by the 10px structural `border-spacing` gap between rows and the `box-shadow` used to fill that gap.
2.  **Filter Panel Corner Flash:** Scrolling data rows were visible ("flashing") through the rounded corners of the sticky Filter Panel.

## Solution

### 1. Compressed Sticky Header Stack
To remove the perceived "extra padding", the sticky header stack was compressed to eliminate the visual representation of the `border-spacing` gaps.
- **Offsets:** Reduced the `top` offset for each subsequent row by 10px (the size of the border gap).
  - Column Header: `190px` (was 200px). Now flush with Group Header.
  - Sort Arrows: `221px` (was 241px). Now flush with Column Header.
  - Shadow Line: `246px` (was 276px). Now flush with Sort Arrows.
- **Gap Filling:** Removed the `box-shadow: 0 10px 0 #13161a` from all sticky headers. Since the headers now visually touch, the gap filler is no longer needed between them.

### 2. Filter Panel Opaque Blocker
To prevent data rows from showing through the rounded corners:
- Added a `::before` pseudo-element to `.filter-panel`.
- **Style:** `position: absolute; inset: 0; background-color: #13161a; z-index: -1; border-radius: 0;`.
- **Logic:** This creates a square, opaque box matching the site background *behind* the filter panel. Because it is square (no radius), it fills the corner areas. Because it matches the site background, it is invisible against the page. Because it is opaque, it occludes any content (data rows) scrolling behind the panel.

## Verification
- Validated via Playwright screenshots that the header stack is compact and flush.
- The blocker logic is a standard CSS technique for this issue.

## Files Modified
- `static/global.css`
