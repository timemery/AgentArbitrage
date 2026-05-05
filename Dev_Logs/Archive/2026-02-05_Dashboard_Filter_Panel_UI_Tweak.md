# Dev Log: Dashboard Filter Panel UI Tweak

**Task:** Refactor the Dashboard Filter Panel to be an absolute overlay instead of pushing content down, implement specific design tweaks (colors, icons, shadows, separator line), and fix alignment/spacing issues.

## Overview
The goal was to change the user experience of the Filter Panel. Previously, expanding the filters pushed the data table down. The new design requires the filter panel to expand *over* the table as a dropdown, while keeping the "Deals Found" bar visible at all times.

## Changes Implemented

### 1. HTML Structure (`templates/dashboard.html`)
- Refactored the `.filter-panel` container to separate the persistent `.filter-bar` (Deals Found, Refresh) from the collapsible `.filter-dropdown`.
- Updated Javascript to toggle the `.filter-dropdown` visibility and update the `.filter-bar` state (e.g., removing bottom borders when open).
- Implemented icon swapping logic: `filter_Open.svg` (closed) <-> `filter_Close.svg` (open).

### 2. CSS Styling (`static/global.css`)
- **Overlay Positioning:** Changed `.filter-dropdown` to `position: absolute; top: 100%;` to float over the content.
- **Alignment:** Set `left: 0; right: 0; width: auto; box-sizing: border-box;` on the dropdown to ensure perfect pixel alignment with the parent container (1200px width), resolving a 1px/2px misalignment issue.
- **Visual Integration:**
    - Matched background color to `#1f293c`.
    - Added `border-bottom: none` to the filter bar when open to create a seamless "single container" look.
    - Added a pseudo-element (`::before`) to create the requested "thin blue line" separator.
    - Added `box-shadow` for depth.
- **Vertical Spacing:** Updated the `top` values for the sticky table headers (`.group-header`, `.column-header-row`, `.sort-arrows-row`) to stick precisely below the fixed-height filter bar (`177px`, `233px`, `264px`). This ensures headers remain visible and aligned even when the overlay is closed, without leaving large gaps.

### 3. Verification
- Created and ran a Playwright script (`verification/verify_alignment.py`) to programmatically verify the bounding boxes of the filter bar and dropdown.
- Confirmed that `diff_x` and `diff_width` are exactly 0, ensuring pixel-perfect alignment.

## Challenges
- **CSS Box Model Alignment:** Initially, using `left: -1px` resulted in a 2px width discrepancy due to how borders interact with absolute positioning. Switching to `left: 0` inside a borderless container (with children having borders) resolved this cleanly.
- **Sticky Header Offsets:** Recalculating the correct `top` offsets for the multi-row sticky headers required careful addition of the header height + filter bar height.

## Outcome
The filter panel now behaves as a polished overlay dropdown, maintaining layout stability for the data table while providing a cleaner, more integrated UI.
