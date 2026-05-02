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
**Files to modify:** `keepa_deals/wsgi_handler.py`, `keepa_deals/xai_advisor.py` (or new module)
- **Definition of "Best Deal":** A deal is not simply the one with the highest raw profit or ROI, as those metrics can sometimes represent noisy data or extreme outliers. Instead, the agent should define "Best Deals" by evaluating the current database inventory against the refined, curated knowledge base.
- **Leveraging Guided Learning Intelligence:**
  - The system contains stored intelligence and mental models within `intelligence.json`, `strategies.json`, and `agent_brain.json` (populated by the Guided Learning features).
  - The backend logic processing the "Best Deals Now" request should read and interpret these strategy files to establish the heuristic criteria for a "Best Deal" (e.g., specific velocity patterns, historical stability, acceptable risk profiles, and optimal price tiers based on the learned personas).
- **On-Demand Data Gathering:**
  - When the user activates the filter and clicks "Apply", the frontend will send an API request (e.g., to `/api/deals/best_deals` or via a special flag in the main deals endpoint) passing the requested limit `N`.
  - The backend will fetch a pool of top candidates from the `deals.db` database (e.g., fetching the top `N * 5` deals sorted by a baseline metric like `Deal Trust` or a composite score).
- **xAI Reasonableness Check:**
  - After gathering the candidate pool, the backend must feed these candidates through an xAI (or equivalent LLM) reasonableness check.
  - The AI should be prompted with the candidate deals' context (ASIN, current price, inferred historical data, drops) alongside the criteria established from the Guided Learning strategies.
  - The AI will score, filter, and rank the candidates to verify that they are *truly* the best, safe, and most logical deals available, eliminating any mathematically sound but logically flawed outliers.
  - The final top `N` verified deals are then returned to the frontend to populate the dashboard table.
