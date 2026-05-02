# Task Description: Implement "Best Deals Now" Filter

## Overview
This document outlines the hypothetical task for implementing the new "Best Deals Now" filter in the Agent Arbitrage dashboard, replacing the "Optimal Filters" feature. **No code execution or testing is required for this current assessment phase.** This guide serves as a blueprint for a future Agent.

## Objectives
1. Deprecate specific existing UI elements by commenting them out (keeping the code for potential future use).
2. Introduce a new filter called "Best Deals Now" that acts as a custom top-N deal selector.
3. Ensure the new feature's UI styling correctly matches existing elements, particularly the "Exclude Conditions" section.

## Instructions for Future Agent

### 1. Update "Exclude Conditions" Filter
**File to modify:** `templates/dashboard.html`
- Locate the "Exclude Conditions" section within the filter panel's bottom row.
- Comment out the HTML for the following condition checkboxes:
  - `U-Like New`
  - `U-Very Good`
  - `U-Good`
- Ensure you add a clear HTML comment stating: `<!-- These features are disabled but kept for potential reactivation by future agents/developers -->`
- The only visible checkboxes remaining in this section should be `New`, `U-Acceptable`, and `Collectible`.

### 2. Deprecate "Optimal Filters"
**Files to modify:** `templates/dashboard.html`, `static/global.css`, `static/js/...` (if separate, else inline in `dashboard.html`)
- Locate the "Optimal Filters" checkbox section in the `.bottom-right-section` of the filter row.
- Comment out its HTML, adding a note that it is being preserved for potential future use.
- Comment out the associated JavaScript logic (e.g., `applyOptimalFilters()` and its event listeners) that handles its functionality, also adding a preservation note.

### 3. Implement "Best Deals Now" UI
**File to modify:** `templates/dashboard.html`
- Create a new UI block to replace the spot where "Optimal Filters" was located.
- **Header:** Add a header `Best Deals Now:` styled with the `filter-group-header` class. It must be visually aligned in the same row as the `Exclude Conditions:` header.
- **Layout Alignment:** The inputs below this header must align horizontally with the `New`, `U-Acceptable`, and `Collectible` checkboxes. You will likely need to wrap this in a `.filter-group-column` to match the structure.
- **Controls Design:**
  - Create a custom control with the text: `Show the top [ 2 ] 🔽 🔼 Best Deals Now.`
  - Include a checkbox to toggle the feature (checked = active, unchecked = inactive).
  - The `[ 2 ]` element acts as a display for the currently selected number of deals.
  - The default value is `2`.
  - The valid choices for this number are strictly: `2, 4, 6, 8, 10, 20, 30, 40, 50, 100`.
  - Implement two buttons for the up (`🔼`) and down (`🔽`) arrows. These should be styled exactly like the ascending/descending arrows used in the table column headers.

### 4. Implement "Best Deals Now" JavaScript Logic
**File to modify:** `templates/dashboard.html` (inside the `<script>` tag)
- Create state variables for the feature's active status and its currently selected value from the allowed list `[2, 4, 6, 8, 10, 20, 30, 40, 50, 100]`.
- Add event listeners to the up/down arrows to cycle through this specific array of values.
- Ensure that clicking the arrows prevents default behavior, does not submit the form unnecessarily if not applied, and strictly bounds the value between `2` and `100` according to the allowed choices.
- Add an event listener to the "Best Deals Now" checkbox to toggle the feature's active state.
- Update the main filtering/fetching logic (e.g., `fetchDeals()`) to include the "Best Deals Now" parameters in its payload when active, so the backend can apply the `LIMIT X` or handle sorting appropriately (or do it client-side if the current architecture applies filters after fetching all).

### 5. Backend Integration (Optional based on Architecture)
**File to modify (if necessary):** `keepa_deals/wsgi_handler.py` or similar backend route handler.
- If pagination/filtering is handled server-side, modify the query builder for `/api/tracking/active_inventory` or `/api/deals` to respect the requested limit and sort by "best" criteria (e.g., highest profit or ROI) when the "Best Deals Now" feature is passed in the query parameters.

### 6. Defining a "Best Deal" and On-Demand Data Gathering
**Files to modify:** `keepa_deals/wsgi_handler.py`, `templates/dashboard.html` (or equivalent backend/frontend logic files)

- **Definition of "Best Deal" (The Hybrid Approach):** A "Best Deal" is defined heuristically as an arbitrage opportunity that exhibits specific, stable historical patterns based on the system's learned intelligence (`intelligence.json`, `strategies.json`). To maintain user trust, we use a "Hybrid / Soft Floor" approach. We define an absolute minimum baseline (a floor) that a deal must meet to be considered "Best." We never show deals below this floor, even if it means returning fewer deals than the user requested.
  - **The Soft Floor Criteria:**
    1.  **Verified Activity:** Must have at least a minimum threshold of inferred sales (e.g., > 1 real drop).
    2.  **Valid Profitability:** Must have a positive ROI and reasonable profit margins, explicitly filtering out astronomical "fake profits" (e.g., capping List Price at $1500).
    3.  **Pattern Recognition:** Ideally exhibits seasonal "wave patterns" and offer count depletion during high-demand periods.
    4.  **Trust Score:** Must have a high `Deal Trust` score.

- **On-Demand Data Gathering (Heuristic Filtering):**
  - When the user activates the filter and clicks "Apply", the frontend sends an API request passing the requested limit `N`.
  - The backend uses a robust **SQL/Heuristic query** to filter the `deals.db` database.
  - The query strictly filters out any deals that fall below the "Soft Floor".
  - It then sorts the remaining qualified deals by relative strength (e.g., highest `Deal Trust` combined with strongest historical drops) and limits the result to `N`.
  - This avoids slow, expensive real-time xAI checks per deal, relying instead on pre-calculated intelligence and strict database constraints.

- **Handling the Edge Case (Fewer Deals than Requested):**
  - If the user requests 20 deals, but the database only has 12 that meet the "Soft Floor" criteria, the system MUST return only 12.
  - **UI Requirement:** The frontend must gracefully handle this scenario to build user trust. If the returned array length is less than `N`, the UI should display a message above or near the table, such as: *"We found [12] slam-dunk deals right now. We refuse to show you bad deals just to hit [20]."*
