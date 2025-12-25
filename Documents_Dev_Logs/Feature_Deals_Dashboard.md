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

*   **Data Grid:** Displays deals in a responsive table. Columns are defined in `Documents_Dev_Logs/Dashboard_Specification.md`.
*   **Filtering:** Users can filter by Keyword, Max Sales Rank, Minimum Profit, ROI, and Category.
    *   *Logic:* Filters are applied client-side (or server-side depending on pagination implementation) to the dataset returned by `/api/deals`.
*   **Sorting:** Columns like "Profit", "Rank", "Update Time" are sortable.
*   **Real-time Updates (The "Janitor"):**
    *   **"Refresh Deals" Button:** Manually triggers the "Janitor" task (`POST /api/run-janitor`) to clean up stale deals (older than 72h) and reload the grid.
    *   **Passive Notification:** The dashboard polls `/api/deal-count` every 60 seconds. This poll includes the current active filters. If the server's filtered count exceeds the local filtered count, a notification ("X New Deals Found") appears, prompting a refresh.
*   **Recalculation:** A "Recalculate" feature allows updating business metrics (Profit, ROI) based on changed settings (Tax, Prep Fee) without re-fetching data from Keepa.

---

## 2. Deals Query Configuration

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

## 3. Data Sourcing (Keepa Scan)

**Route:** `/data_sourcing`
**Template:** `templates/data_sourcing.html`
**Backend Script:** `trigger_backfill_task.py` (calls `keepa_deals/backfiller.py`)

### Overview
This page allows the user to manually trigger a "Backfill" task, which fetches historical or fresh data from Keepa based on the configuration in `keepa_query.json`.

### Features
*   **Start Scan:** Triggers the `trigger_backfill_task.py` script as a background process.
*   **Scan Limit (Optional):** Users can specify a maximum number of deals to process. This is useful for testing or small updates.
*   **Status Tracking:**
    *   **Progress Bar:** Visual indication of the scan status (Running, Completed, Failed).
    *   **Real-time Metrics:** Displays "ETR" (Estimated Time Remaining), processed count, and time per deal.
    *   **Logs:** displays the last few lines of the process output for debugging.
*   **Download Results:** Upon completion, a link to download the results (often a CSV or log) is provided.

### Architecture Note
This feature interacts directly with the `system_state` table in the database to track the "Backfill Page" and "Watermark", ensuring that scans can resume if interrupted.
