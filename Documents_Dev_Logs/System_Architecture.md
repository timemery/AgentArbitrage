# System Architecture & Task Lifecycle

This document outlines the high-level architecture of the **Agent Arbitrage** system, focusing on how the backend components interact to maintain a stable, up-to-date dataset. It is essential for understanding the "invisible" background processes that drive the application.

---

## 1. High-Level Components

The system follows a standard **Flask + Celery + Redis + SQLite** architecture:

*   **Web Server (Flask):** Handles UI rendering (`dashboard.html`), API endpoints (`/api/deals`), and user authentication. It reads from the SQLite database but rarely writes to it (except for user settings).
*   **Async Worker (Celery):** The workhorse. Executes long-running tasks like fetching data from Keepa, analyzing products, and calculating profits. It writes heavily to the SQLite database.
*   **Message Broker (Redis):** Orchestrates communication between Flask and Celery. It also serves as a distributed locking mechanism to prevent task overlaps (e.g., ensuring only one backfill runs at a time).
*   **Database (SQLite):** A single file (`deals.db`) configured for high-concurrency (WAL mode). It stores:
    *   `deals`: The core product data.
    *   `system_state`: Critical metadata (last sync times, backfill progress) that ensures resiliency across restarts.
    *   `user_restrictions`: Data regarding Amazon gating status.
    *   `user_credentials`: Stores SP-API authentication tokens.

---

## 2. The Data Lifecycle (Task Workflows)

There are three primary background tasks that manage the data lifecycle. Understanding the distinction between them is critical.

### A. `backfill_deals` (The Heavy Lifter)
*   **Purpose:** Populates the database with historical data or rebuilds it from scratch.
*   **Trigger:** Manual (CLI or "Danger Zone" button in UI).
*   **Mechanism:**
    1.  Reads the user's query from `keepa_query.json`.
    2.  Iterates through Keepa's result pages (Chunked processing).
    3.  **Resiliency:** Persists its progress (page number) to the `system_state` table. If the server crashes, it resumes from the last checkpoint.
    4.  **Optimized Fetching:** Fetches seller details *only* for the specific seller winning the Buy Box/Lowest Used price to save tokens.

### B. `update_recent_deals` (The Delta Sync)
*   **Purpose:** Keeps the database up-to-date with live market changes without re-scanning the entire catalog.
*   **Trigger:** Scheduled (Cron-like) via Celery Beat (typically every minute).
*   **Mechanism:**
    1.  **Watermark Strategy:** Reads a `watermark_iso` timestamp from `system_state`.
    2.  Queries Keepa for "Products changed since [watermark]".
    3.  Updates only the modified records in the database.
    4.  Updates the watermark timestamp upon completion.
    5.  **Safety:** Checks the Keepa Token Balance before running. If low (buffer < 20), it skips the run to preserve tokens for high-priority tasks.

### C. `clean_stale_deals` (The Janitor)
*   **Purpose:** Removes "zombie" deals (older than 72h by default) to ensure dashboard freshness.
*   **Trigger:** Scheduled (Every 4h) OR Manual (Button: "Refresh Deals" in Dashboard).
*   **Mechanism:** `DELETE FROM deals WHERE last_seen_utc < [72h ago]`.
*   **Benefit:** Prevents the database from growing indefinitely and ensures users only see relevant, active deals.

### D. `check_all_restrictions_for_user` (The Gatekeeper)
*   **Purpose:** Checks Amazon SP-API for restriction status (Gating) on found deals.
*   **Trigger:** Manual (Button: "Re-check Restrictions" in Settings).
*   **Mechanism:**
    1.  Iterates through all ASINs in the `deals` table.
    2.  Queries Amazon SP-API `getListingsRestrictions` endpoint.
    3.  Updates `user_restrictions` table.
    4.  **Error Handling:** If API fails, marks status as `-1` (Error) so UI can display a broken link icon.

### E. `recalculate_deals` (The Logic Refresher)
*   **Purpose:** Updates calculated business metrics (Profit, Margin, All-in Cost) when the user changes their settings (e.g., Prep Fee, Tax Rate).
*   **Trigger:** User action ("Save Settings" button).
*   **Mechanism:**
    1.  Reads all rows from `deals.db`.
    2.  Re-runs the logic in `business_calculations.py` using the new settings and the *existing* raw data (Price, Fees).
    3.  Updates the rows in place.
    4.  **Note:** It does *not* make new API calls to Keepa. It works strictly with local data.

---

## 3. Infrastructure & Resilience

### State Persistence (`system_state` Table)
We do not rely on local files (JSON) for state tracking, as they can be lost during container deployments.
*   **Key Data:** `backfill_page` (Int), `watermark_iso` (Timestamp).
*   **Implementation:** `keepa_deals/db_utils.py` handles the `get_system_state` and `set_system_state` logic.

### User Roles & Authentication
The system supports two distinct user roles:
*   **Admin (`tester`):** Full access to all features, including SP-API token management, Guided Learning, and Strategy extraction.
*   **User (`AristotleLogic`):** Restricted access. Can view the Dashboard and basic Settings but cannot access SP-API controls or AI learning features.
*   **Implementation:** Role is stored in the Flask session upon login. Routes are protected via decorators or conditional checks in `wsgi_handler.py`.

### Process Management (`start_celery.sh`)
The background processes are orchestrated to be resilient:
*   **Worker:** Executes the tasks. Configured with `--concurrency=4` to ensure short tasks (like Janitor or Restriction Checks) are not blocked by long-running Backfills.
*   **Beat:** The scheduler that triggers `update_recent_deals` and `clean_stale_deals`.
*   **Logs:** `celery_worker.log` and `celery_beat.log` are the primary sources for debugging background failures.

### Token Management ("Controlled Deficit")
*   **Strategy:** The system allows the Keepa token balance to dip into the negative (using the bucket allowance) to maximize throughput.
*   **Logic:** If tokens > `MIN_TOKEN_THRESHOLD` (50), requests are allowed even if they cause a deficit. If tokens drop below 50, the system pauses until they refill to 55. This avoids long "refill to max" pauses.
*   **Implementation:** `keepa_deals/token_manager.py`.

### Amazon SP-API Integration
*   **Authentication:** Uses "Login with Amazon" (LWA) Access Tokens via `x-amz-access-token`.
*   **No SigV4:** AWS Signature Version 4 (SigV4) signing and IAM credentials are **not required** for this Private App integration.
*   **Environment:** Supports both Sandbox and Production environments, auto-detecting based on the token validity.

---

## 4. Troubleshooting Guide

*   **"Data isn't updating":** Check `celery_beat.log`. Is the scheduler running? Check `system_state` in the DB—is the watermark advancing?
*   **"The Backfill stalled":** Check `celery_worker.log`. It may be in a "Controlled Deficit" pause, waiting for tokens. This is normal.
*   **"Dashboard is empty":** Verify `db_utils.py` schema matches `dashboard.html` expectations (e.g., column names).
*   **"Spinning/Broken Gated Icon":** Indicates an API failure (timeout or 403). Hover over the icon for details.

## 5. Guided Learning Architecture (xAI Integration)

*   **Input:** Admin user submits URL/Text to `/learn`.
*   **Processing:**
    1.  **Scraper:** Fetches content (supports YouTube transcripts via BrightData).
    2.  **LLM Extraction:** Calls xAI (Grok) in parallel to extract "Strategies" and "Mental Models".
*   **Storage:** Results are reviewed by the user and saved to JSON files (`strategies.json`, `agent_brain.json`).
*   **Usage:** These JSON files are currently for display but will eventually power the agent's decision-making logic.
