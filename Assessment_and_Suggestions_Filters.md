# Assessment and Suggestions: Dashboard Filters

## 1. Executive Summary
The current filtering system provides a solid foundation for finding profitable deals, covering essential metrics like Price, Profit, and Trust. However, it lacks critical velocity indicators (Sales Rank Drops) and nuanced financial metrics (ROI vs. Margin) that are central to the arbitrage strategies outlined in the system's intelligence database.

To elevate the user experience, we recommend implementing an "Optimal Suggested Filters" checkbox (or "Magic Button") that applies best-practice thresholds derived from the system's strategic knowledge base. Crucially, this feature should **preset** the sliders to recommended values while leaving them **adjustable**, allowing users to fine-tune from a solid starting point.

Additionally, we propose adding essential filters for "Min. Drops" and "Min. ROI", implementing user preference persistence, and cleaning up the interface to avoid clutter.

---

## 2. Assessment of Current Filters & Redundancy Analysis

### The "ROI vs. Margin vs. Profit" Debate
The user posed a critical question: *If we have ROI, do we still need Margin and Profit?*

*   **Min. Profit ($):** **MUST KEEP.**
    *   *Reasoning:* ROI is a percentage, Profit is cash. A 100% ROI on a $1 item is only $1 profit. Strategies like "Fast Nickel" still often require a minimum cash floor (e.g., $3 or $4) to cover uncalculated overhead (time, tape, labels). Online arbitrage often demands higher floors than physical sourcing.
*   **Min. ROI (%):** **MUST ADD.**
    *   *Reasoning:* This is the efficiency metric. It prevents users from spending $100 to make $10 (10% ROI), even if the profit ($10) looks okay. It is superior to Margin for measuring capital efficiency.
*   **Min. Margin (%):** **CONSIDER REMOVING / DE-PRIORITIZING.**
    *   *Reasoning:* Margin (Profit / Selling Price) is less actionable for sourcing decisions than ROI (Profit / Cost). If space is tight, Margin is the most redundant metric. However, some sellers are "trained" to think in margin.
    *   *Recommendation:* **Remove "Min. Margin" from the main view** to reduce clutter, replacing it with **"Min. ROI"**.

### Missing Critical Filters
*   **Min. Sales Rank Drops (30d):** The single biggest omission. "Rank" is a snapshot; "Drops" are confirmed sales. High rank + 0 drops = Ghost Listing.
*   **Condition:** Essential for strategic pivots (e.g., "New Only").

---

## 3. The "Optimal Suggested Filters" Feature

**Concept:** A "Magic Button" that applies scientifically derived thresholds based on `intelligence.json` strategies (e.g., "Fast Nickel," "Rule of Thirds").

**Revised Behavior:**
*   **Action:** Checking the box **moves the sliders** to the recommended positions.
*   **Interactivity:** The sliders remain **active**. The user can tweak them (e.g., lower the ROI threshold slightly).
*   **Visual Feedback:** The "Optimal" checkbox remains checked as long as values match the preset. If the user moves a slider, the checkbox creates a visual divergence (e.g., unchecks itself or shows "Customized").
*   **Persistence:** These settings (whether Optimal or Custom) must survive page reloads (saved to `localStorage` or User DB).

**The "Smart" Preset Values:**
*   **Min. Profit:** **$4.00** (Online Arbitrage Floor).
*   **Min. ROI:** **35%** (Aggressive target).
*   **Min. Drops (30d):** **1** (Must have sold recently).
*   **Max. Sales Rank:** **250,000** (Active inventory only).
*   **Min. Deal Trust:** **70%** (Filters out low-confidence data).
*   **Min. Seller Trust:** **Any** (Let the user judge).
*   **Hide Gated:** **ON**.
*   **Hide AMZ:** **ON**.

---

## 4. Proposed UI Mockup (The "Full" Panel)

The goal is to fit these controls into the side panel without overwhelming the user.

```text
+--------------------------------------------------+
|  [ ] Apply Optimal Filters (Ava's Choice)        |  <-- "Magic Button" at top
+--------------------------------------------------+
|  VELOCITY & DEMAND                               |
|  Min. Drops (30d): [ 1 ]------O--------- (Any)   |  <-- New! Critical.
|  Max. Sales Rank:  (10k)------O--------- (Any)   |
+--------------------------------------------------+
|  FINANCIALS                                      |
|  Min. Profit ($):  ($4)-------O--------- (Any)   |
|  Min. ROI (%):     (35%)------O--------- (Any)   |  <-- Replaces Margin
|  Min. Below Avg:   (0%)-------O--------- (Any)   |
+--------------------------------------------------+
|  TRUST & SAFETY                                  |
|  Min. Deal Trust:  (70%)------O--------- (Any)   |
|  Min. Seller Trust:(Any)------O--------- (10)    |
+--------------------------------------------------+
|  EXCLUSIONS                                      |
|  [x] Hide Gated Items                            |
|  [x] Hide Amazon Offers                          |
|  [ ] Condition: [All] [New] [Used] [Col]         |  <-- Dropdown/Toggle
+--------------------------------------------------+
|  [ Apply Filters ]      [ Reset ]                |
+--------------------------------------------------+
```

---

## 5. Technical Requirements & Persistence

### Persistence Strategy
*   **Requirement:** "Settings should stay set between user sessions."
*   **Solution:**
    1.  **Frontend (Immediate):** Save the entire filter state object to `localStorage` (`dashboard_filter_state`). On page load, re-hydrate the form from this state before the first API call.
    2.  **Backend (Robust):** Ideally, save to the `user_preferences` table in the database so settings persist across devices.

### Backend Updates
*   **Query Logic:**
    *   Update `/api/deals` to accept `roi_gte` and `drops_30_gte`.
    *   Implement dynamic ROI calculation in SQL: `(Profit / All_in_Cost) * 100`.
*   **Performance:** Ensure filtering by calculated fields (ROI) doesn't kill query performance on large datasets.

---

## 6. Implementation Roadmap

1.  **Phase 1: The Core Upgrade**
    *   Replace "Min Margin" slider with **"Min ROI"**.
    *   Add **"Min Drops (30d)"** slider.
    *   Implement the **"Optimal Suggested Filters"** checkbox (JS logic to set slider values).
    *   Implement **LocalStorage Persistence** for all filters.
2.  **Phase 2: Refinement**
    *   Add **Condition** filtering (Backend + UI).
    *   Add **Category** filtering.
    *   Implement **User DB Persistence** (cross-device).
