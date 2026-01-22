# Dashboard Rounded Rows UI Update

## Overview
Implemented a major UI refresh for the Dashboard table rows to match the `UI_AA_V2_RoundedRows.png` visual specification. The update introduces rounded corners for all rows ("pills"), distinct separation between column groups, and updated spacing/dimensions.

## Changes

### 1. Dashboard Template (`templates/dashboard.html`)
- **Group Logic:** Updated `renderTable` to identify "Group End" columns (`Condition`, `Detailed_Seasonality`, `last_price_change`, `Profit_Confidence`) and apply the `group-end` class to `th` and `td` elements.
- **Sorting Arrows:** Applied `group-end` logic to the sort arrows row to maintain visual consistency.

### 2. Global Styles (`static/global.css`)
- **Table Structure:**
  - Switched to `border-collapse: separate` with `border-spacing: 0 10px` to create vertical gaps between rows.
  - Removed default borders from cells.
- **Row Styling ("Pills"):**
  - **Correction:** Removed `background-color` from row (`tr`) elements to allow proper border-radius clipping.
  - Applied `background-color` directly to `td` and `th` cells (`#1f293c` Header, `#283143` Data).
  - Applied `border-radius: 8px` to the **first** and **last** cells of every row to creating the "pill" shape.
  - Hover states updated to apply background color to `td` cells.
- **Group Separation:**
  - Implemented `.group-end` with `border-right: 2px solid #13161a`. This uses the site background color to create the illusion of a cut/gap between groups while keeping the row logically connected.
- **Dimensions & Spacing:**
  - **Column Header Height:** Reduced to **31px** (was 34px).
  - **Data Row Height:** Set to **47px**.
  - **Padding:** Enforced `13px` left padding on the first column and `11px` horizontal padding generally.
- **Sticky Header Stack:**
  - Recalculated `top` offsets for sticky elements to account for the header height change (34px -> 31px).
  - **Sort Arrows:** Top offset adjusted to `calc(var(--filter-panel-height) + 221px)`.
  - **Shadow Line:** Top offset adjusted to `calc(var(--filter-panel-height) + 245px)`.

## Technical Notes
- The "Group Separation" relies on the border color matching the body background (`#13161a`). If the background changes, this border color must be updated.
- The Sort Arrows row remains on a transparent (background-matching) row, effectively sitting in the "gap" between the header pill and the first data pill.

## Status
- **Complete:** UI matches the provided red-line mockup specifications.
- **Verified:** Frontend verification script passed and screenshot confirmed rounded corner rendering.
