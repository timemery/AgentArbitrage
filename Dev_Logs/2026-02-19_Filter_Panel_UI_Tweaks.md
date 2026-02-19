# Filter Panel UI Tweaks

**Date:** 2026-02-19
**Agent:** Jules
**Task:** Fix Visual Regressions in Dashboard Filter Panel (Spacing & Shadow Alignment)
**Status:** Success

## Overview
The goal of this task was to resolve two specific visual regressions in the "Deals Dashboard" Filter Panel component:
1.  **Excessive Vertical Spacing:** The gap between the "Deals Found" bar and the Group Headers was incorrectly rendered at 44px, twice the intended 22px.
2.  **Detached Shadow Line:** The shadow element (`#sticky-header-shadow-line`), intended to appear "stuck" to the bottom of the column headers (specifically the sort arrows row), was floating significantly below its target position due to a failed `calc()` operation.

## Challenges Faced

### 1. Environmental Instability
-   Initial attempts to verify the UI were hampered by the need for a fresh sandbox environment. Reusing environments led to instability. The solution required a complete restart with a fresh `dev_deals.db` and `.env` setup.

### 2. Precise Pixel Alignment (The "Sticky Header Stack")
-   The Dashboard's table header is composed of multiple `position: sticky` rows that stack vertically. Their `top` offsets are hardcoded and dependent on the fixed height of the elements above them (the main header and the filter panel).
-   **Structure:**
    -   Main Header: Fixed height (134px).
    -   Filter Panel: Variable height, but effectively treated as fixed for these calculations.
    -   **Group Headers:** `top: 177px`
    -   **Column Headers:** `top: 233px`
    -   **Sort Arrows:** `top: 264px`
-   **The Issue:** The `.filter-panel` had an extraneous `margin-bottom: 22px`. This pushed the subsequent elements down, creating a "double margin" effect (22px margin + 22px padding from the container = 44px gap).
-   **Shadow Issue:** The shadow line's position was being calculated dynamically via a CSS variable that wasn't resolving correctly in the sticky context, causing it to float.

## Solution Implemented

### 1. Spacing Fix (`static/global.css`)
-   **Action:** Explicitly set `margin-bottom: 0px` on the `.filter-panel` class.
-   **Result:** This removed the extra 22px of whitespace, restoring the intended visual rhythm of a single 22px gap between the filter controls and the data table headers.

### 2. Shadow Alignment Fix (`static/global.css`)
-   **Action:** Replaced the dynamic calculation for `#sticky-header-shadow-line` with a hardcoded `top: 289px`.
-   **Calculation:**
    -   `264px` (Top of Sort Arrows Row) + `25px` (Height of Sort Arrows Row) = `289px`.
-   **Result:** The shadow line now sits perfectly flush with the bottom of the sort arrows, providing the intended visual depth cue for the sticky header stack.

## Verification
-   **Method:** Automated Playwright script (`verification/debug_ui.py`) capturing screenshots of the dashboard in both "Before Scroll" and "After Scroll" states.
-   **Outcome:**
    -   `debug_before_scroll.png`: Confirmed the 22px gap.
    -   `debug_after_scroll.png`: Confirmed the shadow line remains attached to the headers during scroll.

## Key Learnings for Future Agents
-   **Fragile CSS Stack:** The dashboard headers rely on a "house of cards" stack of `top` offsets. **Changing the height of the Main Header or the Filter Panel requires manually recalculating all subsequent `top` values (177px, 233px, 264px, 289px).**
-   **Avoid Margins in Sticky Contexts:** Margins on sticky elements or their immediate predecessors can cause unexpected gaps or "double spacing" issues. Prefer padding on the container where possible.
