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

### 6. Defining "Agent's Choice" (The Two-Pass System)
**Files to modify:** `keepa_deals/wsgi_handler.py`, `keepa_deals/xai_advisor.py` (or create a new service module).

To prevent the filter from being a "dumb" mathematical sort (e.g., just returning anything with `profit > 0`), the future agent MUST implement a **Two-Pass Pipeline** that marries high-speed SQL filtering with the nuanced intelligence found in our Guided Learning repositories (`intelligence.json`, `strategies.json`).

#### Pass 1: The Fast SQL Net (The Soft Floor)
The backend must first execute a rigid, mathematical SQL query against `deals.db` to quickly eliminate noise and surface only fundamentally sound candidates. This prevents wasting LLM tokens on bad deals.
- **Strict Profitability & Trust Floor:**
  - `Profit >= 15.00`
  - `ROI >= 30%`
  - `Deal_Trust >= 70`
  - `List_At <= 1500` (Reasonableness cap)
- **Velocity & Freshness Factor:**
  - Calculate a base mathematical score: `(Profit * ROI) * Time_Decay_Factor` (where older deals are penalized).
  - Sort the qualifying deals by this score and **LIMIT to the top 15-20 candidates**.

#### Pass 2: The xAI Strategy Evaluation (The Mastermind)
Once the top 15-20 mathematical candidates are isolated, the system must utilize the xAI API to perform a final, strategic evaluation.
- **Context Injection:** Load the contents of `intelligence.json` and `strategies.json` into the system prompt.
- **Batch Evaluation:** Pass the candidate deals (including their historical drops, current offer counts, and prices) to the LLM in a single batch.
- **Strategic Prompting:** Instruct the AI to evaluate the candidates specifically against the injected strategies:
  - *Look for seasonal "wave patterns" (is this a Q4 book showing signs of life?).*
  - *Analyze the Supply/Demand dynamics (is the offer count dropping significantly, allowing us to dictate price?).*
  - *Identify long-term asset potential with negligible storage risk.*
- **The Output:** The LLM must return a heavily scrutinized subset of these candidates (the true "Prime Picks") along with a confidence score and a 1-sentence reasoning for *why* it fits the strategy.
- **Empty State Handling:** If the LLM determines that none of the candidates truly meet the high standards of a "Prime Pick," the system must gracefully handle the empty array by displaying a UI message: *"We evaluated the database, but no deals currently meet our strict 'Prime Picks' criteria. Check back soon."*

This architecture ensures the filter is not just a mathematical sort, but a true AI-driven curation that leverages all collected platform intelligence.