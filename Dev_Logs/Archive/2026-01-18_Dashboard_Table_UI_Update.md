# Deals Dashboard UI Visual Update

## Context
Applied a comprehensive visual update to the Deals Dashboard table to match strict design specifications. This included adjusting table dimensions, typography, row colors, and replacing graphics for sorting and trend indicators.

## Key Changes

### 1. Table Layout & Dimensions
- **Width:** Fixed to `1333px` to match the Filter Panel.
- **Alignment:** Centered horizontally with `margin: 22px auto 0 auto`.
- **Top Separation:** Added `22px` margin between the filter panel and the table.

### 2. Typography
- **Font Family:** Changed to 'Open Sans' for all table elements.
- **Group Headers:** `15px` Bold, White (`#ffffff`).
- **Column Headers:** `12px` Bold, Grey (`#a3aec0`).
- **Data Content:** `12px` Bold, Grey (`#a3aec0`).

### 3. Row Styling
- **Group Header Row:** Background `transparent`, Border `none`.
- **Column Header Row:** Background `#1f293c`, Border `1px solid #000000` (Top, Bottom, Right; First cell gets Left).
- **Sort Arrows Row:** Background `transparent`, Border `none`.
- **Data Rows:**
  - **Normal:** Background `#283143`.
  - **Hover:** Background `#304163`, Text Color `#ffffff`.
- **Target Height:** Data rows targeted to `48px`.

### 4. Graphics & Icons
- **Sort Arrows:**
  - Replaced generic/old images with specific 17x25px assets: `AscendingOff.png`, `AscendingON.png`, `DescendingOff.png`, `DescendingON.png`.
  - **Interaction:** Implemented JS-based hover effect to swap "Off" state to "ON" state.
  - **Placement:** Left-aligned within the cell.
- **Trend Indicators:**
  - Converted to HTML entities for sharper rendering and specific coloring.
  - **Up (Rising/Bad):** `&#x2191;` (↑) in Red (`#dd080a`).
  - **Down (Falling/Good):** `&#x2193;` (↓) in Green (`#01be0a`).
  - **Flat:** `&rightarrow;` (→) in Orange (`#dc870d`).
  - **Placement:** Strictly placed *before* the numerical/text data.
- **Warning Icon:**
  - Replaced emoji with `&#x26A0;` (⚠) in Orange (`#dc870d`).

### 5. Column Specifics
- **Truncation:**
  - **Title:** Max width `125px`.
  - **Season:** Max width `105px`.
  - Implemented via CSS `text-overflow: ellipsis`.

## Technical Implementation Details
- **CSS:** Updates were applied to `#deals-table` and `.deal-row` classes in `static/global.css`.
- **JavaScript:** `templates/dashboard.html` was modified to inject the new HTML entities and image paths during the `renderTable` execution.
- **Assets:** Renamed `UpArrow_off.png` -> `AscendingOff.png` etc., to align with the new naming convention.

## Verification
- Validated via Playwright script (`verify_dashboard.py`) which successfully navigated to the dashboard and captured a screenshot.
- Manual visual inspection confirmed the layout, colors, and font application match the requirements.
