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

## 2. User Roles & Access Control

The system enforces strict role-based access control (RBAC):

*   **Regular User:**
    *   **Access:** Dashboard (`/dashboard`) and Settings (`/settings`) ONLY.
    *   **Prohibited:** Deals Configuration (`/deals`), Guided Learning (`/guided_learning`), Strategies (`/strategies`), Agent Brain (`/agent_brain`).
*   **Admin User:**
    *   **Access:** All areas.
    *   **Exclusive Features:**
        *   **Guided Learning:** Teaching the AI new concepts.
        *   **Strategies / Agent Brain:** Viewing and managing the AI's knowledge base.
        *   **Deals Configuration:** Editing the `keepa_query.json`.

---

## 3. The Data Lifecycle (Task Workflows)

There are four primary background tasks that manage the data lifecycle.

### A. `backfill_deals` (The Heavy Lifter)
*   **Purpose:** Populates the database with historical data or rebuilds it from scratch.
*   **Trigger:** Manual (CLI or "Danger Zone" button in UI).
*   **Mechanism:**
    1.  Reads the user's query from `keepa_query.json`.
    2.  Iterates through Keepa's result pages (Chunked processing).
    3.  **Constraints:**
        *   **Chunk Size:** Hardcoded to **20** (`DEALS_PER_CHUNK`). Increasing this causes token starvation (bucket empties faster than refill) and must not be changed.
        *   **Locking:** Protected by a Redis Lock (`backfill_deals_lock`) with a **10-day timeout**. This prevents concurrent backfills (which would crash the token manager) while ensuring the lock persists through long-running jobs.
    4.  **Resiliency:** Persists its progress (page number) to the `system_state` table. If the server crashes, it resumes from the last checkpoint.
    5.  **Optimized Fetching:** Fetches seller details *only* for the specific seller winning the Buy Box/Lowest Used price to save tokens.

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
*   **Purpose:** Removes "zombie" deals to ensure dashboard freshness.
*   **Trigger:** Scheduled (Every 4h) OR Manual (Button: "Refresh Deals" in Dashboard).
*   **Mechanism:** `DELETE FROM deals WHERE last_seen_utc < [72h ago]`.
*   **Grace Period:** **72 Hours**. This extended window allows the backfiller sufficient time to cycle through the database and update records before they are deleted.
*   **Benefit:** Prevents the database from growing indefinitely and ensures users only see relevant, active deals.

### D. `check_all_restrictions_for_user` (The Gatekeeper)
*   **Purpose:** Checks Amazon SP-API for restriction status (Gating) on found deals.
*   **Trigger:** Manual (Button: "Re-check Restrictions" in Settings).
*   **Mechanism:**
    1.  Iterates through all ASINs in the `deals` table (Newest first).
    2.  **Batch Processing:** Processes ASINs in batches of **5** to provide incremental UI updates and manage API throughput.
    3.  Queries Amazon SP-API `getListingsRestrictions` endpoint.
    4.  Updates `user_restrictions` table.
    5.  **Error Handling:** If API fails, marks status as `-1` (Error) so UI can display a broken link icon.

---

## 4. AI Components (xAI Integration)

### Guided Learning
*   **Input:** Admin user submits URL/Text to `/learn`.
*   **Processing:**
    1.  **Scraper:** Fetches content (supports YouTube transcripts via BrightData).
    2.  **LLM Extraction:** Calls xAI (`grok-4-fast-reasoning`) in parallel to extract "Strategies" and "Mental Models".
*   **Storage:** Results are reviewed by the user and saved to JSON files (`strategies.json`, `agent_brain.json`).

### Advice from Ava
*   **Route:** `/api/ava-advice/<ASIN>`
*   **Purpose:** Provides real-time, deal-specific analysis in the dashboard overlay.
*   **Mechanism:** Queries `grok-4-fast-reasoning` with the deal's metrics and the "Strategies" context to generate a 50-80 word actionable summary.

---

## 5. Infrastructure & Resilience

### State Persistence (`system_state` Table)
We do not rely on local files (JSON) for state tracking, as they can be lost during container deployments.
*   **Key Data:** `backfill_page` (Int), `watermark_iso` (Timestamp).
*   **Implementation:** `keepa_deals/db_utils.py` handles the `get_system_state` and `set_system_state` logic.

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
