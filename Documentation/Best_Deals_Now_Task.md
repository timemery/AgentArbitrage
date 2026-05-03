# Task Description: Implement "Agent's Choice" Filter

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

### 3. Implement "Agent's Choice" UI
**File to modify:** `templates/dashboard.html`
- Create a new UI block to replace the spot where "Optimal Filters" was located.
- **Header:** Add a header `Agent's Choice:` styled with the `filter-group-header` class. It must be visually aligned in the same row as the `Exclude Conditions:` header.
- **Layout Alignment:** The inputs below this header must align horizontally with the `New`, `U-Acceptable`, and `Collectible` checkboxes. You will likely need to wrap this in a `.filter-group-column` to match the structure.
- **Controls Design:**
  - Create a simple checkbox control with the label: `Prime Picks Only`
  - The checkbox toggles the feature (checked = active, unchecked = inactive).
  - *Note: This replaces the previous complex numerical/arrow design with a streamlined, single-click toggle.*

### 4. Implement "Agent's Choice" JavaScript Logic
**File to modify:** `templates/dashboard.html` (inside the `<script>` tag)
- Create a state variable for the feature's active status.
- Add an event listener to the `Prime Picks Only` checkbox to toggle the feature's active state.
- Update the main filtering/fetching logic (e.g., `fetchDeals()`) to include an `agents_choice=true` parameter in its payload when active, so the backend can apply the elastic filtering and heuristic sorting logic.

### 5. Backend Integration (Optional based on Architecture)
**File to modify (if necessary):** `keepa_deals/wsgi_handler.py` or similar backend route handler.
- If pagination/filtering is handled server-side, modify the query builder for `/api/tracking/active_inventory` or `/api/deals` to respect the requested limit and sort by "best" criteria (e.g., highest profit or ROI) when the "Best Deals Now" feature is passed in the query parameters.

### 6. Defining "Agent's Choice" and Heuristic Filtering
**Files to modify:** `keepa_deals/wsgi_handler.py` (or new module)

- **Definition of "Best Deal":** A "Best Deal" is not simply the item with the highest raw profit or ROI. Based on the system's learned intelligence (`intelligence.json`, `strategies.json`), a "Best Deal" is defined heuristically as an arbitrage opportunity that exhibits specific, stable historical patterns (seasonal wave patterns, significant offer count drops, and high Deal Trust).

- **On-Demand Data Gathering (The Elastic Floor):**
  - Due to API token limitations, the active database may only contain ~300 deals at any given time. A strict, hardcoded numerical floor would frequently result in 0 deals being shown, causing a poor user experience.
  - Instead, implement an **Elastic Floor**. When the `Prime Picks Only` filter is active:
    1.  **Baseline Validation:** The SQL query first filters out any toxic deals (e.g., negative profit, astronomical List Prices > $1500, zero inferred sales).
    2.  **Relative Skimming:** From the remaining valid pool, the system selects the Top X% (e.g., top 5% or 10%). This dynamic slicing ensures the system almost always returns a small, highly curated selection of the *best available* deals, whether that means returning 3 deals or 15 deals, without forcing a specific quota.

- **Freshness and Time Decay Sorting:**
  - In arbitrage, the age of a deal is critical; a great deal found 48 hours ago is likely gone, whereas a good deal found 10 minutes ago is highly actionable.
  - **Time Decay Penalty:** The SQL or Python sorting logic must incorporate a time decay factor based on `last_seen_utc`.
  - A deal's composite score (based on Profit, ROI, and Drops) should be multiplied by a decay coefficient that reduces as the deal ages (e.g., 10 minutes old = 1.0x, 24 hours old = 0.7x).
  - This guarantees that the freshest high-quality opportunities naturally bubble to the top of the `Prime Picks Only` view.

- **Note on xAI Reasonableness Checks:**
  - Real-time xAI checks are **not recommended** for on-demand filtering due to API latency and token costs. The heuristic SQL approach (using pre-calculated Deal Trust, the Elastic Floor, and Time Decay) is the required method for surfacing these deals efficiently.