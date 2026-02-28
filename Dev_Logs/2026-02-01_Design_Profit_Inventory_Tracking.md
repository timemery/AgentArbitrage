# Dev Log: Design of Profit & Inventory Tracking Feature

**Date:** 2026-02-01
**Author:** Jules (AI Agent)
**Status:** Successful Design Phase

## 1. Task Overview
The objective was to design a comprehensive **Profit & Inventory Tracking** system to fill a critical data gap: while the application effectively identifies *potential* deals, it lacked a mechanism to track *realized* profit.

Amazon (via SP-API) provides the Sale Price, but it does not know the user's Buy Cost. The goal was to bridge this gap with a system that combines manual purchase logging with automated sales tracking, creating a "Realized Profit" dashboard that rivals dedicated accounting tools like InventoryLab.

## 2. Key Challenges & Decisions

### Challenge A: The "Buy Price" Data Gap
**Problem:** To calculate profit (`Sale Price - Fees - Buy Cost`), we need the `Buy Cost`. However, entering this data manually for every item is tedious and prone to error. Retroactive entry (weeks after purchase) is often forgotten.
**Solution:** Capture the intent at the source. We redesigned the Dashboard's "Buy" button. Instead of just a passive link to Amazon, it now acts as a data capture trigger, saving the ASIN, Title, and Current Price as a "Potential" purchase.

### Challenge B: Friction vs. Accuracy (The "Buy" Button UX)
**Problem:** We considered a modal popup when clicking "Buy" to ask for the exact cost. However, during high-speed sourcing ("Scouting"), users click "Buy" frequently to check listings. A blocking modal would ruin the workflow.
**Solution:** Adopted a **"Staging" Workflow** (inspired by *Scoutify*).
1.  **Dashboard:** Clicking "Buy" is non-blocking. It silently creates a `POTENTIAL` record in the background.
2.  **Tracking Page:** A new "Potential Buys" tab serves as an inbox. The user reviews these items later (e.g., at the end of the day) and "Confirms" them, converting them to `Active Inventory`. This is where exact costs and SKUs are entered.

### Challenge C: Matching Inventory to Sales
**Problem:** If a user buys the same ASIN multiple times at different costs, how do we know which specific unit sold?
**Solution:** Defined a **FIFO (First-In-First-Out) Reconciliation Logic**.
The system will pair the oldest available inventory unit with the newest incoming Amazon order. This standard accounting practice automates the matching process without requiring the user to manually link every order.

## 3. Technical Architecture Designed

The solution involves a "Matched Ledger" system with three core components defined in `task_tracking_feature.md`:

1.  **Database Schema (`deals.db`):**
    *   `inventory_ledger`: Tracks items from `POTENTIAL` -> `PURCHASED` -> `SOLD_OUT`. Includes `sku` and `buy_cost`.
    *   `sales_ledger`: A mirror of Amazon Orders fetching via SP-API.
    *   `reconciliation_log`: The link table that locks in realized profit for specific units.

2.  **SP-API Integration:**
    *   Identified the need for the `sellingpartnerapi::orders` scope.
    *   Designed the `fetch_amazon_orders` task to pull `OrderStatuses=Shipped` and sync them to the `sales_ledger`.

3.  **UI/UX:**
    *   **Tabbed Tracking Interface:** "Potential" (Inbox), "Inventory" (Assets), "Sales" (P&L).
    *   **Visual Feedback:** Green/Red profit indicators and "Unmatched Sale" warnings to prompt users when cost data is missing.

## 4. Outcome
The task was **Successful**. A complete technical specification and implementation plan (`task_tracking_feature.md`) has been delivered. No code was written (as requested), but the path for the next developer agent is clear:

1.  Execute the Database Migration.
2.  Implement the SP-API Orders fetcher.
3.  Build the Frontend Tabs and "Potential Buy" AJAX workflow.

This design minimizes user friction while maximizing data accuracy, providing a solid foundation for the application's financial analytics features.