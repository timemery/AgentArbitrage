# Feature Specification: "Agent's Choice" Filter

## Overview
This specification outlines the requirements for implementing the "Agent's Choice" (Prime Picks Only) filter. This feature replaces deprecated static filters with an intelligent, two-pass filtering system that leverages dynamic mathematical scoring and xAI strategic evaluation based on our platform's collected intelligence.

---

## 1. UI Modifications

**Target File:** `templates/dashboard.html`

### Deprecate "Exclude Conditions" Options
- Locate the "Exclude Conditions" section in the filter panel.
- Comment out the HTML for `U-Like New`, `U-Very Good`, and `U-Good`.
- Add a clear HTML comment: `<!-- These features are disabled but kept for potential reactivation by future agents/developers -->`
- Retain only `New`, `U-Acceptable`, and `Collectible` as visible options.

### Deprecate "Optimal Filters"
- Comment out the "Optimal Filters" checkbox HTML in the `.bottom-right-section`.
- Comment out the associated JavaScript logic (e.g., `applyOptimalFilters()` and its event listeners) within the `<script>` block.
- Add notes indicating preservation for potential future use.

### Implement "Agent's Choice" Control
- Replace the "Optimal Filters" section with a new UI block.
- Add a header `Agent's Choice:` styled with the `filter-group-header` class.
- Align it horizontally with the `Exclude Conditions:` header.
- Add a simple checkbox control: `Prime Picks Only`.
- Add JavaScript logic to toggle a state variable and include `agents_choice=true` in the backend API request payload (e.g., `fetchDeals()`).

### The Empty State UI
If the backend returns an empty result set while `agents_choice=true` is active:
- Do not display an empty table.
- Display a clear, centered message in the results area: *"We evaluated the database, but no deals currently meet our strict 'Prime Picks' criteria. Check back soon."*

---

## 2. Backend Implementation: The Two-Pass Pipeline

To prevent returning low-quality deals, the filter must use a Two-Pass Pipeline when `agents_choice=true` is present in the request.

### Pass 1: The Smart Floor (SQL & Math)

This pass quickly filters out noise using strict baselines and a dynamic Time Decay factor.

**1. Strict Baseline Filters:**
- `Profit >= 15.00`
- `ROI >= 30%`
- `Deal_Trust >= 70`
- `List_At <= 1500`

**2. Dynamic Time Decay Factor:**
The relevance of a deal decays over time based on its volatility (Sales Rank and Offer Count). A highly ranked textbook with many offers changes price quickly; a slow-moving niche book changes slowly.

- **Base Half-Life (Hours):** `24 + (Sales_Rank / 2,000,000) * 144`
  *(Rank 10k = ~24 hours; Rank 2M = ~168 hours)*
- **Offer Penalty:** Reduce half-life by 2% per current offer, capped at a 50% reduction.
  *Formula:* `Final_Half_Life = Base_Half_Life * (1 - MIN(0.5, Offer_Count * 0.02))`
- **Score Calculation:**
  `Score = (Profit * ROI) * (0.5 ^ (Hours_Since_Last_Seen / Final_Half_Life))`

**3. Execution:**
Sort the qualifying deals by this dynamic `Score` descending, and **LIMIT to the top 20 candidates**.

### Pass 2: The xAI Mastermind (Evaluation)

The top 20 mathematical candidates are now evaluated strategically using xAI. This step is purely for filtering; the LLM's text output is NOT displayed to the user.

**1. Context Assembly:**
- Load `intelligence.json` and `strategies.json`.
- Construct a prompt providing these rules as the "Evaluation Strategy".

**2. Batch Evaluation Request:**
- Send a single batch request to xAI containing the 20 candidates (including Rank, Current Offers, and historical drop context if available).
- **Prompt Instructions:**
  - Evaluate candidates against the provided strategies.
  - Look for seasonal "wave patterns" (e.g., Q4 spikes).
  - Analyze Supply/Demand (is the offer count dropping significantly?).
  - Identify low-risk assets (negligible storage fees for off-season holds).
  - Select ONLY the items that strongly align with these principles.

**3. Final Output:**
- The LLM must return a structured JSON array of selected ASINs.
- The backend filters the top 20 candidates down to only the ASINs selected by the LLM.
- Return these final "Prime Picks" to the frontend.
