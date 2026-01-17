# UI Overhaul: Floating Rows, Sticky Headers, and Scoped CSS

## Overview
Implemented a major UI overhaul for the Deals Dashboard (`templates/dashboard.html` and `static/global.css`) based on the "Floating Row" design specification. This included restructuring the data table, implementing a sticky header system, and creating a collapsible filter panel.

A critical part of this task was resolving a regression where global CSS input styles inadvertently broke the layout of the Login and Settings pages. The solution involved implementing strict CSS scoping for the dashboard components.

## Key Changes

### 1. Floating Row Architecture (`static/global.css`)
- **Concept:** Replaced the standard collapsed-border table model with a separated-border model to create "floating" cards for each deal.
- **Implementation:**
    - `border-collapse: separate`
    - `border-spacing: 0 8px` (Vertical gutter between rows)
    - Row styling applied to `td` elements (border-top, border-bottom) with special handling for the first `td` (border-left, border-top-left-radius, border-bottom-left-radius) and last `td` (border-right, border-right-radius).
    - **Note:** You cannot apply `border-radius` directly to `tr` elements in CSS; it must be applied to the corner cells.

### 2. Sticky Header System
- **Layering:**
    - Group Headers (`top: 0`, Height: 56px)
    - Column Headers (`top: 56px`, Height: 32px)
- **Z-Index Management:** Headers are set to `z-index: 10` to float above the scrolling table body but stay below modals (`z-index: 1050+`).
- **Styling:** Applied `!important` to background colors to prevent transparency issues where content would scroll "under" the header text.

### 3. CSS Scoping & Regression Fixes
- **Problem:** Initial implementation of generic `input[type="text"]` and `.slider` styles in `global.css` caused the Login form fields to shrink and Settings page toggles to break.
- **Solution:**
    - Scoped all dashboard-specific input styles to `.filter-panel input` or specific IDs.
    - Used specific classes (`.login-input`) for the Login page to isolate it from dashboard styles.
    - **Lesson:** Avoid global tag selectors (e.g., plain `input`) in `global.css` as the application grows; prefer BEM-like naming or container-based scoping.

### 4. Visual Polish
- **Typography:** Switched to 'Open Sans' via Google Fonts.
- **Action Buttons:** Implemented "Pill" style buttons (Green 'Buy', Orange 'Gated', Red 'Restricted') with precise dimensions (28px x 52px).
- **Trend Indicators:** Integrated HTML entity arrows (⬇, ⬆) and colored classes (`.trend-falling-green`, `.trend-rising-red`) for instant visual comprehension of price/offer trends.

## Verification
- **Automated:** `verify_ui.py` (Playwright) was used to capture screenshots of Dashboard, Login, and Settings pages.
- **Visual:** Confirmed that the "Floating Row" effect works, headers stick correctly on scroll, and the Filter Panel expands/collapses as intended (92px height).
- **Regression:** Confirmed Login and Settings pages retain their original bootstrap/clean styling.

## Artifacts
- **Provided Assets:** `refresh.svg` and `filter.svg` are now permanent assets in `static/`.
- **Cleaned:** `verification/` folder and `cookies.txt` were removed post-verification.
