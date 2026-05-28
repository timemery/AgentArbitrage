# Feature Documentation: Tracking (Potential Buys, Active Inventory, Sales & Profit)

This document details the functionality, logic, and specifications for the Tracking page, which closes the loop from deal discovery through realized profit. It is the operational counterpart to the Deals Dashboard.

For background data flow and database schema, see **`System_State.md`** and **`System_Architecture.md`**.

---

## 1. Overview

**Route:** `/tracking`
**Template:** `templates/tracking.html`
**Primary APIs:** `/api/tracking/active`, `/api/tracking/sales`, `/api/tracking/potential`

The Tracking page is the post-discovery workflow tool. Once a user acts on a deal from the Dashboard, the Tracking page becomes the surface where that purchase is monitored from "potential buy" through "live inventory" through "realized sale."

It is built on three tabs, each backed by paginated SP-API-fed endpoints rather than monolithic loads to keep the page responsive at scale.

| Tab | Purpose | Source |
| :--- | :--- | :--- |
| **Potential Buys** | Sourcing leads marked for purchase but not yet shipped to Amazon. | `inventory_ledger` (status flag) |
| **Active Inventory** | Units currently at Amazon (fulfillable, inbound working, shipped, receiving). | SP-API + `inventory_ledger` |
| **Sales & Profit** | Realized sales with FIFO-matched buy costs to produce true realized profit. | SP-API Orders + `sales_ledger` |

### Shared UI Standards
*   **Visual Style:** Tracking uses the same `strategies-table` dark theme as the Dashboard. This is intentional — users move between Dashboard and Tracking constantly and the visual continuity reduces cognitive load.
*   **Pagination:** All three tabs use the unified pagination component (`static/js/pagination.js`) shared with the Dashboard (numbered buttons 1–5 + Prev/Next, current page highlighted). This was harmonized in May 2026.
*   **Sticky Headers:** Sticky column headers with scroll-triggered shadow mask, matching Dashboard behavior.
*   **Deep Links:** ASIN and SKU values are rendered as hyperlinks — ASIN links to the Amazon product page, SKU links to the Seller Central Manage Inventory view filtered to that SKU.
*   **Sorting:** Client-side sorting matching Dashboard behavior on every column.

---

## 2. Potential Buys

### Purpose
Bridges the gap between "I saw a deal" and "I bought it and shipped it to Amazon." This is the lead-stage workflow that competitor sourcing tools (Tactical Arbitrage, SellerAmp, ScoutIQ, BookMine) either omit entirely or treat as a saved-search folder.

### Data Captured
*   **ASIN, Title, Condition** — pulled from the deal at the moment of action.
*   **Buy Cost** (`buy_cost_paid`) — the user's actual paid price (book price + actual shipping + actual tax, excluding Prep Fee and Amazon fees). **Editable inline.**
*   **Estimated Profit, Margin, ROI** — recalculated live as the user edits the buy cost.
*   **List at Price** — the recommended price carried over from the deal evaluation.
*   **Date Added, Status** — when the lead entered the system, current pipeline state.

### Editable Buy Cost Logic (Critical)
When the system initially ingests a Potential Buy, the buy cost (`buy_cost_paid`) is an **estimate** carried from the deal data. When the user actually purchases the item, they edit the buy cost inline:
*   The system sets `buy_cost_confirmed = TRUE` in `inventory_ledger`.
*   All downstream profit, margin, and ROI calculations recalculate against the confirmed cost.
*   Unconfirmed estimates are visually distinguished (lighter shade / italic) to prompt the user to verify them.

This solves a universal FBA-tracking pain point: every competitor's profit math is only as good as its cost data, and most cost-entry workflows are opaque batch operations rather than inline edits at the point of decision.

---

## 3. Active Inventory

### Purpose
Show every unit the user currently has in the Amazon FBA system, regardless of fulfillment state.

### Data Captured
*   **ASIN, SKU, Title, Condition** — full identification, including the ASIN column that the system natively stores rather than reconstructing through JOINs.
*   **Quantity by State:**
    *   **Fulfillable** (units ready to sell)
    *   **Inbound Working** (received in user's facility, not yet shipped to Amazon)
    *   **Inbound Shipped** (in transit to an Amazon fulfillment center)
    *   **Inbound Receiving** (arrived at Amazon, not yet checked in)
*   **Buy Cost** (`buy_cost_paid`) — original cost from the matched `inventory_ledger` row (editable inline, with confirmation flag as in Potential Buys).
*   **List Price, Estimated Profit, Margin, ROI** — calculated against the confirmed buy cost.

### Data Sources
The Active Inventory tab pulls live state from the SP-API on demand (via "Sync from Amazon") and persists snapshots to `inventory_ledger`. The ASIN is stored natively on every row, eliminating the table-join indirection that complicates inventory tracking in InventoryLab and Sellerboard.

### Bulk Cost Import (CSV)
For users with large existing inventory, two CSV flows are exposed under an expandable "Bulk edit via CSV" link (demoted from the primary UI to avoid clutter):
*   **Download Missing Costs CSV** — generates a CSV of every inventory row missing a confirmed buy cost.
*   **Upload Costs CSV** — accepts the same column structure back, populating buy costs in bulk.

The download → fill → upload loop is the bridge for users migrating from spreadsheets or other tools. The CSV columns are the same on both ends to make the round-trip obvious.

---

## 4. Sales & Profit

### Purpose
Show what the user actually sold and what they actually made on each unit, with the buy cost matched to the sale via FIFO (First-In, First-Out).

### Data Captured
*   **Order ID, Order Date** — from SP-API Orders v0.
*   **ASIN, SKU, Title, Condition** — from the matched order item.
*   **Sale Price** — realized sale price from `sales_ledger`.
*   **Buy Cost (Matched)** — the original `buy_cost_paid` from the corresponding `inventory_ledger` row, matched via FIFO.
*   **Realized Profit, Margin, ROI** — dynamically calculated by the same profit-calculation logic that powers the Deals Dashboard (all-in cost vs. sale price net of actual FBA/referral fees).

### Why Fees Aren't a Column
The SP-API Orders v0 endpoint does not return fee data — that requires a separate Finances API integration. Rather than show $0.00 fees (which is misleading), the Sales & Profit tab shows **realized profit** computed using the actual sale price and estimated fees (until API limits are resolved, the true model dictates subtracting actual fees). Fees are immaterial as a displayed value as long as the user can see whether each unit was actually profitable.

### FIFO Matching
When a sale lands in `sales_ledger`, the system finds the oldest matching `inventory_ledger` row (same ASIN, status `Active`) with units remaining and decrements one unit. The buy cost from that specific row is locked into the sale record. This produces accurate realized profit even when the same ASIN was purchased multiple times at different prices.

---

## 5. Competitive Position

The Tracking page exists because no single competitor closes the loop from sourcing → buy → inventory → realized profit in one tool. A May 2026 audit of seven comparable tools (ZenArbitrage, InventoryLab, Tactical Arbitrage, SellerAmp, ScoutIQ, BookMine, Sellerboard) found:

*   Only **InventoryLab** and **Sellerboard** offer real post-buy tracking.
*   **Four of the seven** are pre-buy sourcing tools with no inventory tracking at all.
*   A cottage industry of paid Excel/Google Sheets templates (Caleb Roth's free Book Flipper spreadsheet has 155 ratings; Gumroad sellers charge $14–$50) exists because the gap is real and unsolved.

The full audit lives at `Documentation/Business_Documents/Research/Tracking_UX_Audit.md`.

### Pain Points Specifically Addressed
*   **Cost entry hairball** — every competitor struggles with where buy cost comes from. Inline-editable buy cost at the Potential Buys stage (the point where the user knows the number) plus a confirmation flag is the solution.
*   **ASIN/SKU tab-hopping** — both identifiers are hyperlinks to their respective Amazon pages, eliminating the manual copy/paste that competitors force.
*   **Fee reconciliation discrepancies** — InventoryLab's own support docs admit their fees won't match Amazon (deferred posting + DD+7 reserves). The Tracking page sidesteps this by computing realized profit from confirmed cost + sale price, rather than from estimated fees that drift against Amazon's actual settlements.
*   **Spreadsheet workarounds** — by tying sourcing → inventory → realized profit in one place, the Tracking page removes the need for a separate spreadsheet workflow.

---

## 6. Architectural Notes

*   **No monolithic loads.** Every tab paginates server-side.
*   **Shared profit logic.** The same backend function calculates projected profit on the Dashboard and realized profit in Sales & Profit. There is no second source of truth.
*   **SP-API LWA-only authentication.** No AWS IAM signing. See `Token_Management_Strategy.md` Section 3.
*   **Editable cost confirmation flag.** `buy_cost_confirmed` is the single boolean that gates whether downstream profit math treats a cost as authoritative.
