# System Architecture & Task Lifecycle

This document outlines the high-level architecture of the **Agent Arbitrage** system, focusing on how the backend components interact to maintain a stable, up-to-date dataset. It is essential for understanding the "invisible" background processes that drive the application.

---

## 1. High-Level Components

The system follows a standard **Flask + Celery + Redis + SQLite** architecture:

*   **Web Server (Flask):** Handles UI rendering (`dashboard.html`), API endpoints (`/api/deals`), and user authentication. It reads from the SQLite database but rarely writes to it (except for user settings).
*   **Async Worker (Celery):** The workhorse. Executes long-running tasks like fetching data from Keepa, analyzing products, and calculating profits. It writes heavily to the SQLite database.
*   **Message Broker (Redis):** Orchestrates communication between Flask and Celery. It also serves as a distributed locking mechanism to prevent task overlaps.
*   **Database (SQLite):** A single file (`deals.db`) configured for high-concurrency (WAL mode). It stores:
    *   `deals`: The core product data.
    *   `system_state`: Critical metadata (watermark timestamps) that ensures resiliency across restarts.
    *   `user_restrictions`: Data regarding Amazon gating status.
    *   `user_credentials`: Stores SP-API authentication tokens.

---

## 2. User Roles & Access Control

The system enforces strict role-based access control (RBAC):

*   **Regular User:**
    *   **Access:** Dashboard (`/dashboard`) and Settings (`/settings`) ONLY.
    *   **Prohibited:** Deals Configuration (`/deals`), Guided Learning (`/guided_learning`), Strategies (`/strategies`), Intelligence (`/intelligence`).
*   **Admin User:**
    *   **Access:** All areas.
    *   **Exclusive Features:**
        *   **Guided Learning:** Teaching the AI new concepts.
        *   **Strategies / Intelligence:** Viewing and managing the AI's knowledge base.
        *   **Deals Configuration:** Editing the `keepa_query.json`.

---

## 3. The Data Lifecycle (Task Workflows)

The data lifecycle is primarily managed by the **Smart Ingestor**, with supporting maintenance tasks.

### A. Smart Ingestor v3.0 (The Unified Engine)
*   **Purpose:** The single, unified entry point for all deal ingestion. Replaces the legacy `backfiller` and `update_recent_deals` tasks.
*   **Trigger:** Scheduled every minute via Celery Beat (`keepa_deals.smart_ingestor.run`).
*   **Mechanism:**
    1.  **Watermark Check:** Loads the `watermark_iso` timestamp from `system_state`. If missing or corrupt, defaults to 24 hours ago.
    2.  **Delta Fetch:** Queries Keepa for all products updated since the watermark.
    3.  **Decoupled Batching Strategy:**
        *   **Stage 1: Peek (Discovery):** Fetches lightweight stats for **50 ASINs** at once.
            *   **Dynamic Scaling:** Automatically reduces to **20** if refill rate < 20/min, and to **5** if refill rate < 10/min.
            *   **Filter:** Checks `check_peek_viability` to reject dead/irrelevant items (e.g., no Used history) before spending heavy tokens.
        *   **Stage 2: Commit (Analysis):** Survivors of the Peek filter are processed in smaller batches of **5 ASINs** (Heavy Fetch) to prevent "Deficit Shock" (instantly draining 1000+ tokens).
        *   **Stage 3: Light Update:** Existing deals are refreshed in large batches (50 ASINs) using lightweight stats.
    4.  **Watermark Ratchet:** The watermark is updated to the `lastUpdate` timestamp of the *last processed deal* in the current batch. This ensures progress is tracked even if all deals in a batch are rejected.
    5.  **Zombie Defense:** Automatically detects "Zombie" deals (missing critical data like `List at`) and forces a heavy re-fetch to repair them.

### B. `clean_stale_deals` (The Janitor)
*   **Purpose:** Removes "zombie" deals to ensure dashboard freshness.
*   **Trigger:** Scheduled (Every 4h).
*   **Mechanism:** `DELETE FROM deals WHERE last_seen_utc < [72h ago]`.
*   **Grace Period:** **72 Hours**. This extended window allows the ingestor sufficient time to cycle through and update records before they are deleted.

### C. `check_all_restrictions_for_user` (The Gatekeeper)
*   **Purpose:** Checks Amazon SP-API for restriction status (Gating) on found deals.
*   **Trigger:** Manual (Button: "Re-check Restrictions" in Settings) or triggered automatically by the Smart Ingestor for new deals.
*   **Mechanism:**
    1.  Iterates through ASINs in the `deals` table.
    2.  **Batch Processing:** Processes ASINs in batches of **5**.
    3.  Queries Amazon SP-API `getListingsRestrictions` endpoint.
    4.  Updates `user_restrictions` table.

---

## 4. AI Components (xAI Integration)

### Guided Learning
*   **Input:** Admin user submits URL/Text to `/learn`.
*   **Processing:**
    1.  **Scraper:** Fetches content (supports YouTube transcripts via BrightData).
    2.  **LLM Extraction:** Calls xAI (`grok-4-fast-reasoning`) in parallel to extract "Strategies" and "Mental Models".
*   **Storage:** Results are reviewed by the user and saved to JSON files (`strategies.json`, `intelligence.json`).

### Advice from Ava
*   **Route:** `/api/ava-advice/<ASIN>`
*   **Purpose:** Provides real-time, deal-specific analysis in the dashboard overlay.
*   **Mechanism:** Queries `grok-4-fast-reasoning` with the deal's metrics and the "Strategies" context to generate a 50-80 word actionable summary.

### Mentor Chat
*   **Route:** `/api/mentor-chat`
*   **Purpose:** Persistent, persona-driven chat interface for general business strategy and mentorship.
*   **Mechanism:**
    *   **Personas:** Supports 4 distinct personas (Olyvia/CFO, Joel/Flipper, Evelyn/Professor, Errol/Quant) defined in `ava_advisor.py`.
    *   **Context:** Injects the full "Strategies" and "Intelligence" knowledge base into the system prompt.
    *   **Model:** Uses `grok-4-fast-reasoning` (Temperature 0.5) for detailed, contextual responses.

---

## 5. Infrastructure & Resilience

### State Persistence (`system_state` Table)
We do not rely on local files (JSON) for state tracking, as they can be lost during container deployments.
*   **Key Data:** `watermark_iso` (Timestamp).
*   **Implementation:** `keepa_deals/db_utils.py` handles the `get_system_state` and `set_system_state` logic.

### Process Management (`start_celery.sh`)
The background processes are orchestrated to be resilient:
*   **Worker:** Executes the tasks.
*   **Beat:** The scheduler that triggers `smart-ingestor-run` and `clean_stale_deals`.
*   **Zombie Locks:** The `kill_everything_force.sh` script invokes `Diagnostics/kill_redis_safely.py` to perform a "Brain Wipe" (FLUSHALL + SAVE) on Redis during restarts.
*   **Logs:** `celery_worker.log` and `celery_beat.log` are the primary sources for debugging background failures.

### Token Management ("Controlled Deficit")
*   **Strategy:** The system allows the Keepa token balance to dip into the negative (Deficit Spending) to maximize throughput.
*   **Architecture:** **Distributed Token Bucket (Redis-backed)**.
*   **Deficit Protection:** Enforces a hard limit of `MAX_DEFICIT = -180`. If a request would push the balance below this, it is blocked to prevent API lockouts.
*   **Lock Release:** If the required wait time exceeds 60 seconds (deep recharge), the `TokenManager` raises a `TokenRechargeError`. The Smart Ingestor catches this and immediately releases the Redis lock, freeing the worker for other tasks.

### Amazon SP-API Integration
*   **Authentication:** Uses "Login with Amazon" (LWA) Access Tokens via `x-amz-access-token`.
*   **No SigV4:** AWS Signature Version 4 (SigV4) signing and IAM credentials are **not required** for this Private App integration.
*   **Environment:** Supports both Sandbox and Production environments, auto-detecting based on the token validity.
