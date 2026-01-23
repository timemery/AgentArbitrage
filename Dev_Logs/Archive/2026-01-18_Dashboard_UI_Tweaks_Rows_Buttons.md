# Dashboard UI Tweaks: Rows, Buttons & Hover

## Context
Implemented specific UI tweaks to the Dashboard table rows and action buttons based on user feedback. The goal was to refine the visual hierarchy, fix hover behaviors, and standardize button dimensions and colors.

## Key Changes

### 1. Column Header Row
- **Height:** Explicitly set to `32px` to reduce vertical space.
- **Visuals:**
  - Fill Color: `#1f293c` (Maintained).
  - Border: `1px solid #000000` (Maintained).
- **CSS:** Updated `#deals-table th` with `height: 32px; vertical-align: middle;`.

### 2. Data Row Hover Effect
- **Issue:** The hover effect was not changing text color to white because the ID-based cell selector (`#deals-table td`) had higher specificity than the class-based hover selector (`.deal-row:hover td`).
- **Fix:** Increased specificity of the hover selector to `#deals-table .deal-row:hover td`.
- **Result:** Text color now correctly transitions to `#ffffff` on hover.

### 3. Action Buttons (Buy & Gated)
- **Standardization:** Both buttons now share identical dimensions and layout properties via the base `.approval-link` class.
- **Dimensions:**
  - **Outer Box:** **56px width x 32px height** (using `box-sizing: border-box`).
  - **Inner Content:** This effectively yields a **52px x 28px** clickable area plus the 2px border, matching the Filter Panel buttons exactly.
- **Styling:**
  - **Buy Button (Green):**
    - Fill: `#034106`
    - Border: `2px solid #06610b`
    - Class: `.btn-buy`
  - **Gated Button (Orange/Apply):**
    - Fill: `#8a3c04`
    - Border: `2px solid #a54805`
    - Class: `.btn-gated`
- **Implementation:**
  - Removed inline styles from `templates/dashboard.html` JavaScript generation.
  - Added specific CSS classes in `static/global.css`.
  - Updated the "View" fallback button to maintain consistent sizing with a grey theme.

## Technical Details
- **File(s) Modified:**
  - `static/global.css`: CSS rule updates.
  - `templates/dashboard.html`: JavaScript `renderTable` logic update.
- **Verification:** Verified changes via file inspection.

## Reference Styles
```css
.approval-link {
    width: 56px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    box-sizing: border-box;
    /* ... */
}
.btn-buy {
    background-color: #034106 !important;
    border: 2px solid #06610b;
}
.btn-gated {
    background-color: #8a3c04 !important;
    border: 2px solid #a54805;
}
```
