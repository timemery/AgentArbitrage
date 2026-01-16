# Task Description: UI Overhaul Implementation

## Goal
Implement the new "Floating Row" UI, Sticky Headers, and Filter Panel based on the provided mockups and specifications. This is a frontend-focused task involving CSS refactoring and HTML structure updates in `templates/dashboard.html` and `static/global.css`.

## Environment & Constraints
*   **Start with a Fresh Sandbox.**
*   **Read-Only Access:** Do NOT read logs, archives, or cache files.
*   **Assets:** Required graphics (Ascending/Descending, Filter icons) are available in `/tmp/file_attachments/`. Move them to `static/` as needed.

## 3-Phase Implementation Plan

### Phase 1: Structural Foundation (The "Bones")
*   **Floating Rows (CSS Refactor):**
    *   Target: `#deals-table` (or main data table).
    *   CSS Property: `border-collapse: separate;`
    *   Vertical Spacing (Gutter): `border-spacing: 0 8px;`
    *   **Row Styling:**
        *   Height: `47px` (Content) + `1px` Border = ~49px Total.
        *   Background: `#1f293c` (Apply to `td`, not `tr` directly if using standard table CSS hacks for rounded corners).
        *   Border: `1px solid #000000`.
            *   *Implementation Note:* Apply top/bottom borders to all `td`s. Apply left border to first `td`, right border to last `td`.
        *   Border Radius: `8px`.
            *   *Implementation Note:* Apply `border-top-left-radius` and `border-bottom-left-radius` to the first `td`. Apply right-side radii to the last `td`.
    *   **Row Hover State:**
        *   Background: `#304163`.
        *   Outer Border: `#000000` (1px).

### Phase 2: Functional Layout (The "Mechanics")
*   **Sticky Headers:**
    *   Implement `position: sticky` for the table headers (`th`).
    *   Reserved Top Height: ~135px.
        *   *Note:* The mockup implies the Top Navigation + Filter Bar + Column Headers occupy the top ~135px. Ensure `z-index` is managed so headers stay above content but below modals/overlays.
*   **Filter Panel:**
    *   State: Collapsible.
    *   Height: `92px` (When open).
    *   Background: `#1f293c`.
    *   Border: `#7397c2` (1px).
    *   Components: Contains "Hide Gated", "Hide AMZ" toggles, and "Reset" button.

### Phase 3: Visual Polish (The "Paint")
*   **Typography:**
    *   Font Family: `Open Sans` (Load from Google Fonts if not present, replacing current system font).
    *   Column Headers: `Bold 12px`, White (`#ffffff`).
    *   Row Data: `12px`, White (`#ffffff`).
    *   Secondary Text (e.g., labels, sub-values): Light Grey (approx `#a3aec0`).
*   **Action Buttons (Pills):**
    *   **Buy (Green):** Fill `#034106`, Border `#06610b`.
    *   **Gated (Orange):** Fill `#8a3c04`, Border `#a54805`.
    *   **Restricted (Red):** Fill `#8a0404`, Border `#a50505` (Inferred from pattern, or use `#ff4d4d` style).
    *   Dimensions: `28px` Height x `52px` Width.
    *   Border Radius: `8px`.
    *   Alignment: Center vertically in the row.
*   **Trend Arrows & Icons:**
    *   **Right Arrow (➡):** Orange `#dc870d` (HTML Entity `&rarr;` or similar).
    *   **Up Arrow (⬆):** Red `#dd080a`.
    *   **Down Arrow (⬇):** Green `#01be0a`.
    *   **Warning Triangle (⚠):** Orange `#dc870d`.
    *   **Refresh Icon:** Use provided `refresh.svg`.
    *   **Filter Icon:** Use provided `filter.svg`.
