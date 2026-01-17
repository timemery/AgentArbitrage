# Dashboard Filter Panel UI Update

## Context
Implemented a comprehensive UI overhaul for the Dashboard Filter Panel based on provided mockups (`FilterPanel_Update_OPEN.png`, `FilterPanel_Update_CLOSED.png`). The update introduced a collapsible panel, specific color schemes, custom slider controls, and strict state management for applying and resetting filters.

## Key Changes

### 1. Collapsible Filter Panel
- **Structure:** Replaced the static filter form with a collapsible container (`.filter-panel`) that transitions between two states:
  - **Closed:** 42px height, displaying summary stats ("Deals Found", "New Deals", "Refresh").
  - **Open:** 92px height, revealing 6 slider controls and action buttons.
- **CSS Classes:**
  - `.filter-panel`: Base container styling (Background `#1f293c`, Border `#000000`, Radius 8px).
  - `.filter-panel-closed` / `.filter-panel-open`: Manage height transitions.
  - `.panel-content-closed` / `.panel-content-open`: Toggle visibility of internal content.
- **Typography:** Explicitly enabled font smoothing (`-webkit-font-smoothing: antialiased`) for cleaner text rendering.

### 2. Custom Slider Controls
- Implemented standard `<input type='range'>` elements with custom webkit styling.
- **Track:** 132px width, 10px height, color `#304163`.
- **Thumb:** 18px circle, color `#566e9e`.
- **Thumb Border:** Implemented as a **2px inner border** using `box-shadow: inset 0 0 0 2px #7397c2` to increase visual weight without affecting element dimensions.
- **Labels:** Open Sans Bold 12px, White. Readout values `#a3aec0` with exactly **8px spacing** from the header text.

### 3. Action Logic (Apply vs. Reset)
- **Apply Button:**
  1. Reads values from hidden inputs updated by sliders.
  2. Triggers `fetchDeals()` with new parameters.
  3. Closes the panel.
  4. Resets the "New Deals" counter.
- **Reset Button:**
  1. Resets visual sliders to their default positions (mostly 0/Any, Sales Rank to Max).
  2. Updates hidden input values.
  3. **Crucial:** Does NOT trigger a fetch. This allows users to reset and then optionally tweak before applying.

### 4. Toggle Interaction & Icons
- **Selector Logic:** The toggle button ID changes based on state:
  - To **Open**: Click `#filter-icon-closed`.
  - To **Close**: Click `#filter-icon-open`.
- **Assets:**
  - `filter.svg`: 24x24px, utilized for the main toggle.
  - `refresh.svg`: Updated to a clean 24x24 viewBox but sized to **16x16px** via CSS (`.refresh-link-panel img`).
- **Refresh Link:** explicitly removed hover underline (`text-decoration: none`).

### 5. "New Deals" Notification
- Logic updated to strictly hide the "New Deals found" text (`display: none`) when the count is 0, both on initial load and when manually refreshing via the link.

## Reference Code Snippets

**CSS for Refresh Icon Sizing:**
```css
.refresh-link-panel img {
    width: 16px;
    height: 16px;
}
```

**JavaScript Toggle Logic:**
```javascript
function toggleFilterPanel(open) {
    if (open) {
        filterPanel.classList.remove('filter-panel-closed');
        filterPanel.classList.add('filter-panel-open');
    } else {
        filterPanel.classList.remove('filter-panel-open');
        filterPanel.classList.add('filter-panel-closed');
    }
}
filterIconClosed.addEventListener('click', () => toggleFilterPanel(true));
filterIconOpen.addEventListener('click', () => toggleFilterPanel(false));
```

## Verification
- Validated via Playwright script (`verify_final.py`) capturing screenshots of both Open and Closed states.
- Confirmed correct rendering of stacked "Apply"/"Reset" buttons (28x52px).
