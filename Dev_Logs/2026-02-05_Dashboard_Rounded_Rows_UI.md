# Dashboard Sticky Header Fix & Refinement

## Overview
Addressed a regression where the new `border-spacing: 0 10px` introduced to create "pill" rows caused the sticky header stack to overlap ("squish") during scroll. The vertical spacing acted as extra margin that was not accounted for in the sticky top offsets.

## Changes

### 1. Global Styles (`static/global.css`)
- **Recalculated Sticky Offsets:** Updated `top` values for sticky elements to explicitly account for the `10px` gap between each row.
  - **Column Headers:** Increased offset by 10px (`190px` -> `200px`).
  - **Sort Arrows:** Increased offset by 20px (`221px` -> `241px`) (Accumulated gaps).
  - **Shadow Line:** Increased offset by 30px (`245px` -> `275px`) (Accumulated gaps).
- **Gap Filling:** Added `box-shadow: 0 10px 0 #13161a` to sticky header cells (`.group-header th`, `.column-header-row th`, `.sort-arrows-row td`).
  - **Purpose:** This projects a solid 10px block of the site background color *below* the sticky element. This visual "filler" hides the scrolling content that would otherwise be visible through the transparent 10px gap caused by `border-spacing`.
  - **Result:** The headers stack solidly without bleed-through, while maintaining the required spacing for the data row "pills".

## Technical Notes
- The math relies on the `border-spacing` being exactly `10px`. If spacing changes, all `top` offsets and `box-shadow` values must be updated.
- The `box-shadow` approach is cleaner than adding pseudo-elements or borders because it moves with the sticky element automatically and respects the table cell box model.

## Status
- **Unsuccessful:** The task was closed by the user as the changes did not have the desired effect.
- **Outstanding Issues:**
  - Extra padding/margin/spacing above the Group Headers was **NOT** removed.
  - Extra padding/margin/spacing both above and below the Ascending/Descending arrows was **NOT** removed.
- **Action:** Code submitted as-is to preserve state for the next attempt.
