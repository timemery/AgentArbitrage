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
**Files to modify:** `keepa_deals/wsgi_handler.py` (or new module)

- **Definition of "Best Deal":** A "Best Deal" is not simply the item with the highest raw profit or ROI, as those metrics alone can represent noisy data, one-off anomalies, or extreme outliers. Based on the system's learned intelligence (found in `intelligence.json` and `strategies.json`), a "Best Deal" is defined heuristically as an arbitrage opportunity that exhibits specific, stable historical patterns:
  1.  **Seasonal Arbitrage Potential:** Books/items that show clear "wave patterns" in historical data—prices and competition are low in off-seasons (e.g., summer) and reliably spike during high-demand periods (e.g., Q4/holidays).
  2.  **Supply-Demand Dynamics:** A strong indicator of a "Best Deal" is a historical pattern where the *offer count drops significantly* (e.g., from 30+ down to near zero) during peak seasons, which naturally drives the price up.
  3.  **Sales Velocity (Rank):** A corresponding drop in Sales Rank (indicating increased popularity) exactly when the offer count depletes.
  4.  **Negligible Storage Risk:** Items that meet these criteria are considered "Best Deals" even if they won't sell immediately, because the strategy explicitly values them as long-term assets where Amazon FBA storage fees (e.g., 3-4 cents over several months) are negligible compared to the eventual high-margin payoff.

- **On-Demand Data Gathering (Heuristic Filtering):**
  - When the user activates the filter and clicks "Apply", the frontend will send an API request passing the requested limit `N`.
  - Instead of a slow, expensive real-time xAI check for every deal, the backend should use a robust **SQL/Heuristic query** to filter and sort the `deals.db` database.
  - The query should rank deals by prioritizing:
    - High `Deal Trust` score (indicating data reliability).
    - Consistent historical inferred sales drops (`Drops > X`).
    - Favorable offer count trends (if tracked in the DB).
    - Expected ROI and Profit that fit within reasonable, non-astronomical bounds (e.g., filtering out `$1000+` fake profits).
  - This heuristic approach efficiently surfaces the top `N` deals that mathematically match the learned strategies without the latency or cost of an on-the-fly LLM evaluation.

- **Note on xAI Reasonableness Checks:**
  - The xAI check is **not recommended** for on-demand filtering when the user clicks "Apply" due to API latency, token costs, and rate limits.
  - Instead, the intelligence gathered from the strategies should be hardcoded into the backend's SQL query parameters and Python sorting logic. The pre-calculated `Deal Trust` and existing backend reasonableness caps (e.g., max $1,500 list price) already serve as the primary defense against hallucinations.
