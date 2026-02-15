# Verification: Zero Profit Deal Persistence and Filtering

## Overview
The objective of this task was to verify and ensure that the system supports the persistence of deals with **zero or negative profit**, or **missing pricing data** (e.g., `List at`, `1yr. Avg.`), while simultaneously **filtering them out** from the user-facing Dashboard. This allows the system to track potentially valuable items that are currently unprofitable, enabling future re-evaluation via lightweight updates if prices improve, without cluttering the UI with "bad" data.

## Implementation Details

### 1. Ingestion Layer (`keepa_deals/processing.py`)
-   **Behavior Confirmed:** The ingestion logic no longer rejects deals solely due to `Profit <= 0` or missing `List at` / `1yr. Avg.` values.
-   **Action:** These deals are now processed and returned as valid `row_data` to be saved to the database.

### 2. Smart Ingestor Logic (`keepa_deals/smart_ingestor.py`)
-   **Zombie Detection Update:** The "Zombie Data" detection logic (which forces heavy re-fetches for bad data) was updated to **ignore** missing price data or negative profit.
-   **Preventing Loops:** This ensures the system does not enter an infinite loop of fetching a deal, rejecting it as "bad data", and then re-fetching it again because it's still missing from the DB or flagged as incomplete. The deal is simply saved as-is.

### 3. Database Schema (`keepa_deals/db_utils.py`)
-   **Column Sanitization:** Verified that column names are sanitized.
    -   `List at` -> `List_at`
    -   `1yr. Avg.` -> `1yr_Avg`
-   **Persistence:** Zero-profit deals are successfully stored in the `deals` table.

### 4. Dashboard Filtering (`wsgi_handler.py`)
-   **API Logic:** The `/api/deals` and `/api/deal-count` endpoints were updated/verified to enforce strict filtering:
    -   `"Profit" > 0`
    -   `"List_at" IS NOT NULL` AND `> 0`
    -   `"1yr_Avg" IS NOT NULL` AND `!= 0` AND NOT IN ('-', 'N/A', '')
-   **Result:** Users only see profitable, actionable deals. The "bad" deals remain in the background database for tracking.

### 5. Cleanup (`keepa_deals/janitor.py`)
-   **Retention Policy:** Stale deals (including these zero-profit ones) are retained for **72 hours** before being purged, allowing a 3-day window for price recovery.

## Challenges & Solutions
-   **Column Name Ambiguity:** Initial verification scripts failed due to using raw JSON keys (`List at`) instead of sanitized DB column names (`List_at`).
    -   *Solution:* Verified schema using `sqlite3` PRAGMA commands and updated verification scripts to use correct column names.
-   **Verification Complexity:** Confirming "absence" of data in the UI while presence in DB required a dedicated diagnostic script.
    -   *Solution:* Created `Diagnostics/verify_zero_profit_fix.py` to insert a test record and query both the DB directly and the API endpoint to confirm disparate results.

## Outcome
**Success.** The system correctly persists unprofitable deals for future potential while keeping the user experience clean. No new code changes were required during this verification phase as the logic was already correctly implemented in previous steps.

*Verified by: Jules (AI Agent)*
*Date: 2026-02-15*
