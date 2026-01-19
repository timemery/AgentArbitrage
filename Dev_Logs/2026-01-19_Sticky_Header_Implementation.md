# Sticky Header Implementation

**Date:** 2026-01-19  
**Status:** Successful  
**Task:** Sticky Header - Scroll while keeping Column Headers Visible

## Overview
The goal was to implement a robust sticky header system for the Deals Dashboard. This required ensuring that the Main Navigation, Filter Panel, Group Headers, Column Headers, and Sort Arrow rows remained visible at the top of the viewport when the user scrolls down the data table. 

Key constraints included:
- **Dynamic Awareness:** The sticky stack had to adjust automatically when the Filter Panel expanded (102px) or collapsed (43px).
- **Visual Separation:** A full-width (browser width, not just table width) shadow line was required to appear *only* when scrolling occurred.
- **Visual Integrity:** Data rows scrolling behind the headers could not "bleed through"; headers needed opaque backgrounds that matched the site's dark theme/gradient.

## Challenges & Solutions

### 1. Dynamic Stacking Context
**Challenge:** The Filter Panel has two states with different heights. Standard `position: sticky` requires fixed `top` offsets, which would break when the panel resized.
**Solution:** 
- Introduced a CSS variable `--filter-panel-height` in `global.css`.
- Updated this variable via JavaScript (`templates/dashboard.html`) whenever the filter toggle button is clicked.
- Used `calc()` for all subsequent sticky elements. For example, the Column Headers' `top` position is calculated as:
  ```css
  top: calc(var(--filter-panel-height) + 134px + 32px); /* Filter + MainHeader(134px) + GroupHeader(32px) */
  ```

### 2. Data Bleed-Through
**Challenge:** The user requested "No fill" initially for some elements to preserve the gradient background, but this caused data rows to be visible behind the sticky headers during scroll, creating a visual mess.
**Solution:** 
- Applied specific opaque background colors to the sticky elements.
- `.main-header`: `#000000` (Matches the top of the site gradient).
- Table Headers (`th`) and Sort Rows: `#15192b` (Deep blue/black matching the lower site background).
- This ensures the headers look "transparent" relative to the page theme but are functionally opaque to the scrolling content beneath.

### 3. Full-Width Scroll Shadow
**Challenge:** The table has a specific width (1333px), but the shadow line needed to span the entire browser width (`100vw`) and only appear when scrolling started.
**Solution:**
- Created a dedicated `div` (`#sticky-header-shadow-line`) outside the table container.
- Set `position: fixed`, `width: 100vw`, and `z-index: 180` (below headers, above content).
- Added a JavaScript `scroll` event listener to toggle `display: block/none` based on `window.scrollY > 10`.

## Reference Implementation Details

### Stack Order (Z-Index)
- **Main Header:** `z-index: 300` (Topmost)
- **Filter Panel:** `z-index: 200`
- **Group/Column Headers:** `z-index: 190`
- **Shadow Line:** `z-index: 180`
- **Table Data:** Default (0)

### CSS Variables
- `--filter-panel-height`: Controls the base offset for table headers. Defaults to `43px` (Closed).

### JavaScript Logic
The `toggleFilterPanel` function in `dashboard.html` now manages the CSS variable:
```javascript
function toggleFilterPanel(open) {
    if (open) {
        // ... classes ...
        document.documentElement.style.setProperty('--filter-panel-height', '102px');
    } else {
        // ... classes ...
        document.documentElement.style.setProperty('--filter-panel-height', '43px');
    }
}
```

## Files Modified
- `static/global.css`: Added sticky positioning, Z-indices, and background colors.
- `templates/dashboard.html`: Added shadow line element and scroll listener logic.

## Future Considerations
- If the Main Header height (134px) changes, the hardcoded `134px` values in the `calc()` definitions in `global.css` will need to be updated. Moving this to a CSS variable (e.g., `--header-height`) would be a good refactor.
