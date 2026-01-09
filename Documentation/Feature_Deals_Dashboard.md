# Feature Documentation: Deals, Dashboard & Data Sourcing

This document details the functionality, logic, and specifications for the Deals Dashboard, Query Configuration, and Data Sourcing features.

---

## 1. Deals Dashboard

**Route:** `/dashboard`
**Template:** `templates/dashboard.html`
**API Endpoint:** `/api/deals` (`wsgi_handler.py`)

### Overview
The Dashboard is the central hub for viewing and analyzing arbitrage opportunities. It presents a grid of deals sourced from Keepa, enriched with calculated metrics (Profit, ROI, Sales Rank), and allows for powerful filtering and sorting.

### Key Features

*   **Data Grid:** Displays deals in a responsive table. Columns are defined in `Documentation/Dashboard_Specification.md`.
*   **Filtering:** Users can filter by Keyword, Max Sales Rank, Minimum Profit, Margin, Profit Confidence (Trust), Seller Trust, and Price Drops.
    *   *Logic:* Filters are applied server-side by the `/api/deals` endpoint SQL query.
    *   **"Any" Logic:** Setting a filter to 0 ("Any") excludes it from the query, ensuring that NULL/Negative values are not hidden by default.
*   **Sorting:** Columns like "Profit", "Rank", "Update Time" are sortable.
*   **Real-time Updates (The "Janitor"):**
    *   **"Refresh Deals" Button:** Manually triggers the "Janitor" task (`POST /api/run-janitor`) to clean up stale deals (older than **72 hours**) and reload the grid.
    *   **Passive Notification:** The dashboard polls `/api/deal-count` (filtered) every 30 seconds. It compares this count against the local filtered record count. If the server count differs, a notification ("New Deals Available") appears.
*   **Recalculation:** A "Recalculate" feature allows updating business metrics (Profit, ROI) based on changed settings (Tax, Prep Fee) without re-fetching data from Keepa.

### Gated Column States
The "Gated" column indicates the user's restriction status on Amazon:
*   **Spinner:** Check is pending/queued.
*   **Green Check:** Approved / Not Restricted.
*   **Red X:** Restricted. (Clicking opens "Apply to Sell").
*   **Broken Icon (⚠):** API Error (e.g., Timeout, 403 Forbidden). Hovering shows "API Error".

### Advice from Ava (AI Overlay)
When expanding a deal's details:
*   An "Advice from Ava" section appears prominently at the top of the overlay.
*   It asynchronously fetches an AI analysis (`/api/ava-advice/<ASIN>`) powered by `grok-4-fast-reasoning`.
*   Provides 50-80 words of actionable advice based on the deal's specific metrics.

---

## 2. Deals Query Configuration (Admin Only)

**Access Control:** This feature is strictly restricted to **Admin** users. Regular users cannot access this page.

**Route:** `/deals`
**Template:** `templates/deals.html`
**Storage:** `keepa_query.json`

### Overview
This page acts as a configuration interface for the Keepa API query used during the "Data Sourcing" (Backfill) process.

### Functionality
*   **JSON Editor:** Provides a text area to edit the raw JSON query object.
*   **Validation:** On submission (`POST /deals`), the backend attempts to parse the JSON. If invalid, an error is flashed, and the file is not saved.
*   **Persistence:** Valid queries are saved to `keepa_query.json` in the root directory. This file is read by `trigger_backfill_task.py` to determine which products to fetch from Keepa.

---

## 3. Data Sourcing (Hidden)

**Note:** The explicit "Data Sourcing" page has been removed from the navigation menu for all users as of Phase 1 Access Control updates. Backfill operations are now primarily managed via CLI or automatic scheduled tasks, though the endpoints and scripts remain functional in the backend.

### Architecture Note
The backfill process interacts directly with the `system_state` table in the database to track the "Backfill Page" and "Watermark", ensuring that scans can resume if interrupted.
