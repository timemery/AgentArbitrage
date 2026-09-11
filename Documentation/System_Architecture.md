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
*   **Trigger:** Scheduled every 5 minutes via Celery Beat (`keepa_deals.smart_ingestor.run`, configured as `crontab(minute='*/5')`).
*   **Mechanism:**
    1.  **Watermark Check:** Loads the `watermark_iso` timestamp from `system_state`. If missing or corrupt, defaults to 24 hours ago.
    2.  **Delta Fetch:** Queries Keepa for all products updated since the watermark.
    3.  **Decoupled Batching Strategy:**
        *   **Stage 0.5: Stale Deal Rescue:** Before the main sync, the system proactively queries for deals older than **48 hours**.
            *   **Action:** Fetches fresh lightweight stats for up to **20** such deals per run.
            *   **Purpose:** Prevents valid, stable deals (which may not appear in Keepa's delta feed) from expiring and being deleted by the Janitor after 72 hours.
            *   **Eligibility is 48 hours to the second (Sept 2026 fix).** The cutoff is built in Python with `.isoformat()` and bound as a parameter, matching both the format every `last_seen_utc` writer uses and the cutoff `janitor.py` compares against. Previously it used SQLite's `datetime('now', '-48 hours')`, which formats with a space where the stored values use `T`; compared as TEXT, `T` sorts after a space, so a row became eligible not at 48h but at the first 00:00 UTC after that — **at age 72h minus its last-seen UTC time of day**, against a Janitor that deletes at 72h exactly. The intended 24-hour rescue window was therefore between 4 and 24 hours depending on time of day, and rows last seen shortly after midnight UTC became rescuable at almost the same moment they became deletable. The same defect and the same fix apply to the Ghost Restriction Sweeper's 1-hour cutoff, where it delayed re-queueing a stuck gating check until the next UTC day. Guarded by `tests/test_stale_cutoff_format.py`.
            *   **Persists (Sept 2026):** the refreshed `Sales_Rank_Current`, `Offers`, `Offers_180`, `Offers_365`, `last_price_change`, `All_in_Cost` and `Min_Listing_Price`. Before this fix the rescue silently wrote the **old** rank, offer counts and all-in cost back while storing a `Profit` and `Margin` computed from the **new** cost, leaving rescued rows internally inconsistent.
            *   **Persists only what it can actually compute.** This path fetches with `history=0` and, unlike the main Light Update, never merges a Keepa deal object into the product — its ASINs are the ones the deal feed has stopped returning, which is why they went stale. `last_price_change` consequently has neither a `csv` history nor a `currentSince` array to read and returns its `-` sentinel on **every** call here. No-data sentinels are skipped rather than written, so the stored value survives, across all six columns that can carry one: `Sales_Rank_Current`, `Drops`, `Offers`, `Offers_180`, `Offers_365` and `last_price_change`. The preserved reading can be days old on this path and is shown as current — see "LIGHTWEIGHT PRESERVATION RULE" in `Data_Logic.md` for the full trade-off.
        *   **Stage 1: Peek (Discovery):** Fetches lightweight stats for **50 ASINs** at once.
            *   **Dynamic Scaling:** Automatically reduces to **20** if refill rate < 20/min, and to **15** if refill rate < 10/min (optimized to fit within the 40-token burst).
            *   **Filter:** Checks `check_peek_viability` to reject dead/irrelevant items. `salesRankDrops365` threshold lowered to **1** (from 4) to capture "Silver Standard" (low velocity) candidates.
        *   **Stage 1.5: XAI Rescue:** If initial analysis finds 0 confirmed sales or no offer drops, the system calls **xAI** to identify "Hidden Sales" (rank drops without offer drops), rescuing potentially valid deals from rejection.
        *   **Stage 2: Commit (Analysis):** Survivors of the Peek filter are processed in smaller batches of **5 ASINs** (Heavy Fetch) to prevent "Deficit Shock" (instantly draining 1000+ tokens).
        *   **Stage 3: Light Update:** Existing deals are refreshed in large batches (50 ASINs) using lightweight stats.
            *   **Ceiling Check:** Enforces that the `List at` price does not exceed 90% of the current Amazon New Price, preventing "fake profit" on preserved deals. (Currently gated OFF via `ENABLE_LIGHTWEIGHT_CEILING_CLAMP`.)
            *   **Preserves (Sept 2026):** every column the heavy pass computed that a lightweight fetch cannot recompute — `List_at`, `1yr_Avg`, `Deal_Trust`, `Expected_Trough_Price`, the seasonality strings and all 180/365-day aggregates. Before this fix the upsert read these by `headers.json` display name off a row keyed by sanitized DB column names and wrote **215 of 246 columns as NULL on every light update**. See "DATA LOSS INCIDENT (Sept 2026)" in `Data_Logic.md`.
    4.  **Watermark Ratchet:** The watermark is updated to the `lastUpdate` timestamp of the *last processed deal* in the current batch. This ensures progress is tracked even if all deals in a batch are rejected.
    5.  **Data Persistence Strategy (formerly Zombie Defense):** The aggressive re-fetching logic for 'Zombie' deals (missing critical data like `List at`) was found to cause infinite loops and token waste. It has been replaced by a **Persistence Strategy** where deals with missing data are saved and updated via standard 'Lightweight Updates', allowing for gradual data repair without system strain.
    6.  **Upsert (shared):** Both the Stale Rescue and the main Smart Ingestor loop write through `upsert_deal_rows` in `keepa_deals/db_utils.py`, the single builder for the deals `ON CONFLICT(ASIN) DO UPDATE` statement. The main loop upserts heavy and light rows **in the same batch**, so heavy rows (built keyed by `headers.json` display names) are re-keyed with `to_db_keys` before they are appended. It derives its column list from `headers.json` via `sanitize_col_name`, the same transform `recreate_deals_table` uses to CREATE the table, so the write contract and the schema cannot drift apart. Rows handed to it **must** be keyed by sanitized DB column names. Do not reimplement this SQL at a call site.

        *   **Recovery caveat:** `recalculator.py` / `run_deals_migration.py` cannot repair rows damaged by an upsert defect. `List_at` derives from `infer_sale_events`, which needs the Keepa `csv` history arrays that are never stored in `deals.db`. Rebuilding it requires a fresh heavy fetch (~20 tokens/ASIN). See the warning in `Documentation/Feature_Deals_Dashboard.md` under Recalculation.

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

### D. `generate_prime_picks` (Agent's Choice Evaluator)
*   **Purpose:** Evaluates deals to find the top "Prime Picks" for the dashboard's Agent's Choice filter, using a two-pass pipeline.
*   **Trigger:** Automatically chained after the `clean_stale_deals` task, or manually via a `/api/prime_picks/refresh` POST request.
*   **Mechanism:**
    1.  **Pass 1 (Smart Floor):** SQL/math based filtering and time-decay scoring to select the top 20 candidates. It uses the `Used_Offer_Count_365_days_avg` for safe offer-trend deduplication, and incorporates a 'Year-Round Velocity Cap' (`PASS_1_YEAR_ROUND_VELOCITY_CAP = 2000000`) that explicitly rejects non-seasonal items with a rank > 2,000,000 to drop structurally weak candidates.
    2.  **Pass 2 (xAI Mastermind):** Passes candidates to `grok-4-fast-reasoning` with heavily filtered strategies to identify the best deals. Includes a 'SEASONAL HIGH-RANK CORRECTION' to explicitly prevent the AI from rejecting seasonal candidates solely based on their current high (off-season) sales rank.
    3.  **Caching:** Saves the final results to the `prime_picks` table atomically. If Pass 2 fails (e.g. xAI API error), the system gracefully skips updating the cache to preserve the previous valid results.

### E. One-Time Maintenance Scripts (Manual, Never Scheduled)

Both follow the same safety pattern and neither is a Celery task: run from the
application root as `www-data`, with all background services stopped. Dry run by
default, `--apply` to delete, **no `--force`** — every safety check is mandatory.

Shared guards: preflight aborts if Celery or the `monitor_and_restart` watchdog is
running, if the `smart_ingestor_lock` Redis key is held, or if the process is not
`www-data`. Each takes its own backup through SQLite's backup API rather than
`backup_db.sh` (a plain `cp` that can miss committed pages still sitting in
`deals.db-wal`) and verifies the copy by row count. The delete runs as one
transaction with no `VACUUM` — the Janitor already VACUUMs on large deletions and
doing it here would rewrite the whole file outside the transaction. Both write a
verified backup and the target ASIN list to `db_backups/` (gitignored) so the
re-acquisition rate can be measured later. Scope is the `deals` table only;
`user_restrictions`, `prime_picks`, `confirmed_buys` and the `system_state`
watermark are untouched, so there is **no watermark rewind** and re-acquisition is
passive, depending on Keepa surfacing the ASIN in the deal feed again.

**Why deleting is the repair, in both cases.** While a row exists the ingestor always
routes its ASIN to the light path: `existing_asins_set` is rebuilt from a live
`SELECT` every run and the Zombie Data Defense heavy re-fetch is commented out, so
`is_zombie` is always `False`. Stale Rescue is light-only, and the recalculator is
API-free. **No code path can restore these rows in place** — `1yr_Avg` and `List_at`
derive from `infer_sale_events`, which needs the Keepa `csv` history that `deals.db`
never stores. Deleting is not the cheaper option, it is the only mechanism that
returns the ASIN to the heavy path.

#### `cleanup_low_est_rows.py` — current

*   **Purpose:** Deletes the rows whose `1yr_Avg` came from the Keepa
    listing-average fallback removed on 2026-09-11 (audit B-6).
*   **Predicate:** `"Deal_Trust" = 'Low (Est.)'`. That marker is the **only**
    persisted fingerprint: the `price_source` flag that drove it is computed but
    never stored, because it is not in `headers.json` and `upsert_deal_rows` drops
    it. The match is exact, so it cannot catch the other non-numeric Deal Trust
    state, `'-'` (the XAI no-offer-drops rescue), which must survive.
*   **Invariant:** zero rows with `"Deal_Trust" = 'Low (Est.)' AND "1yr_Avg" IS
    NULL`. The marker was only ever written on the branch where the fallback had
    just returned a value, so that combination would mean the marker is no longer
    tracking the value it is supposed to mark. Chosen to stay true after the
    fallback removal, and once no code path writes the marker it holds vacuously.
*   **Known blind spot:** rows that used the fallback but escaped the marker. The
    `"Low (Est.)"` write was the last statement of a `try` block that also ran
    `get_trend`, `get_percent_discount`, `recent_inferred_sale_price` and
    `analyze_sales_rank_trends`; an exception in any of those was swallowed, leaving
    the fallback value with a normal numeric Deal Trust. Those rows are
    indistinguishable in SQL. Bounded: a leaked row that is also dashboard-visible
    needs every one of its inferred sales to be older than 365 days.
*   **Guarded by:** `tests/test_cleanup_low_est_rows.py`.

#### `Archive/scripts/recover_damaged_deals.py` — spent, archived 2026-09-11

*   **What it did:** the one-time recovery for the A-7 light-update defect (PR #330).
    Run once on 2026-09-11, deleting 1,543 rows. See
    `Dev_Logs/2026-09-11_Q2_Recover_A7_Damaged_Rows.md`.
*   **Why it is archived and must not be run again.** Its mandatory invariant
    asserted that **zero** rows have `"1yr_Avg" IS NULL AND "List_at" IS NOT NULL`,
    and its predicate rationale rested on `1yr_Avg IS NULL` being a reliable damage
    fingerprint (the heavy path wrote that column on 295 of 295 rows at the A-7
    baseline). **Removing the fallback retires both.** `List at` is computed over a
    3-year window and `1yr. Avg.` over a 1-year one, so a book whose inferred sales
    are all older than 365 days now legitimately has a valid `List_at` with a NULL
    `1yr_Avg`. The script would abort on a healthy database, and its abort message
    would tell the reader to investigate a state that is now correct.

---

## 4. AI Components (xAI Integration)

### Platform Knowledge (Self-Awareness)
*   **Module:** `keepa_deals/platform_knowledge.py`
*   **Purpose:** Reads and caches specific Markdown documentation files from the `Documentation/` directory.
*   **Integration:** This text is injected into AI system prompts, allowing models to answer questions based on the platform's actual logic and specifications, effectively making the AI "self-aware."

### Guided Learning
*   **Input:** Admin user submits URL/Text to `/learn`.
*   **Processing:**
    1.  **Scraper:** Fetches content (supports YouTube transcripts via BrightData).
    2.  **LLM Extraction:** Calls xAI (`grok-4-fast-reasoning`) in parallel to extract "Strategies" and "Mental Models".
*   **Storage:** Results are reviewed by the user and saved to JSON files (`strategies.json`, `intelligence.json`).

### Advice from Ava
*   **Route:** `/api/ava-advice/<ASIN>`
*   **Purpose:** Provides real-time, deal-specific analysis in the dashboard overlay.
*   **Mechanism:** Queries `grok-4-fast-reasoning` with the deal's metrics, the "Strategies" context, and the shared `STRATEGIC_CORRECTIONS` block from `keepa_deals/ava_advisor.py` to generate a 50-80 word actionable summary. The dual-strategy framing in the corrections ensures unbiased evaluation of both high-velocity flips and seasonal holds.
*   **Strategy Cap:** `load_strategies()` injects a bounded slice, not the whole file — 'High' confidence only, at most `MAX_STRATEGIES_PER_CATEGORY` (30) per category, drawn from the fixed `STRATEGY_CORE_CATEGORIES` allowlist (General, Risk, Buying, Pricing), plus Seasonality when the deal is a textbook. This mirrors the Pass 2 "Tiered Strategy Injection" bound. See "Advisor Context Caps" below.

### Mentor Chat
*   **Route:** `/api/mentor-chat`
*   **Purpose:** Persistent, persona-driven chat interface for general business strategy and mentorship.
*   **Mechanism:**
    *   **Personas:** Supports 4 distinct personas (Olyvia/CFO, Joel/Flipper, Evelyn/Professor, Errol/Quant) defined in `ava_advisor.py`.
    *   **Context:** Injects a **capped** slice of the "Strategies" and "Intelligence" knowledge bases, alongside the shared `STRATEGIC_CORRECTIONS` block (for dual-strategy framing and overriding overcautious textbook/high-rank rules) into the system prompt. See "Advisor Context Caps" below.
    *   **Model:** Uses `grok-4-fast-reasoning` (Temperature 0.5) for detailed, contextual responses.

### Advisor Context Caps (September 2026)

`strategies.json` (8.4 MB) and `intelligence.json` (1.1 MB) grow without bound via Guided Learning. Until September 2026 the Advisor helpers in `keepa_deals/ava_advisor.py` injected them **whole**: `load_strategies()` called with no `deal_context` (Mentor Chat) emitted every strategy in every category, and `load_intelligence()` emitted every idea. A single Mentor Chat message therefore carried roughly 9.5 MB / ~2.4M tokens of prompt. The "Tiered Strategy Injection" cap added in May 2026 was applied only to Prime Picks Pass 2 (`prime_picks_task.get_tiered_strategies()`) and never propagated to the Advisor.

Both helpers are now bounded by module-level constants in `keepa_deals/ava_advisor.py`:

*   **`STRATEGY_CORE_CATEGORIES`** = `("General", "Risk", "Buying", "Pricing")` — fixed allowlist, so a new category appearing in the file cannot grow the prompt.
*   **`MAX_STRATEGIES_PER_CATEGORY`** = `30` — 'High' confidence only. Ceiling: 120 strategies, or 150 when the textbook context adds Seasonality.
*   **`MAX_INTELLIGENCE_ITEMS`** = `150` — `intelligence.json` has no category dimension to tier on, so a flat leading slice bounds it. 150 gives parity with the strategies ceiling.

Both now emit output whose size is independent of file size. Measured against a production-sized synthetic corpus: Mentor Chat ~2.4M tokens → **~16,000**; Ava advice unbounded → **~22,900** (the remainder is dominated by the ~12,055-token `platform_knowledge` doc set, which is a separate, uncapped input).

**Note:** legacy plain-string entries in `strategies.json` (pre-schema, no `category`/`confidence`) are skipped, matching `get_tiered_strategies()`. Only dict-shaped strategies are injected.

### AI-Triggered Hover Tooltips
*   **Route:** `/api/tooltip/<term>`
*   **Purpose:** Provides instant context for UI elements (headers, filters) on the Deals Dashboard.
*   **Mechanism:** Queries the AI using the `platform_knowledge` context to define UI terms. To ensure zero latency and save tokens, responses are stored permanently in `tooltip_cache.json`.

### Agent's Choice Mastermind (Pass 2)
*   **Task:** `generate_prime_picks` (Celery background task)
*   **Purpose:** Evaluates a curated list of candidate deals against the system's learned knowledge base to find the absolute best options.
*   **Mechanism:**
    *   **Model:** Uses `grok-4-fast-reasoning`. This model must be strictly used to prevent hallucinations or empty array returns.
    *   **Payload Optimization:** Employs "Tiered Strategy Injection" via `get_tiered_strategies()`. Rather than injecting all 14,000+ strategies, it limits core categories to 30 'High' confidence rules and dynamically injects relevant category rules based on the candidates' metadata, preventing 504 Gateway Timeouts and context window overflows.

---

## 5. Infrastructure & Resilience

### Database Connections & mod_wsgi (Critical)
To prevent SQLite lock-contention and 504 Gateway Timeouts, the system enforces the following architecture:
*   **Centralized Helper:** All connections must be made via `keepa_deals.db_utils.get_db_connection()`, which standardizes `busy_timeout=5000` and `journal_mode=WAL`.
*   **Context Managers:** Database assignments MUST be wrapped in a `with` context block (or closed via `finally`) to prevent unclosed connections from leaking and deadlocking `PRAGMA` execution.
*   **Apache mod_wsgi (WSGI Hangs):** Because the application heavily uses C-extensions like `sqlite3` and `numpy`, it cannot run safely inside isolated mod_wsgi sub-interpreters. C-extension deadlocks within these sub-interpreters will cause WSGI requests to hang entirely without throwing Python tracebacks in the Apache logs. To resolve this, the live production Apache configuration (`/etc/apache2/sites-enabled/agentarbitrage.conf`) **must** include the `WSGIApplicationGroup %{GLOBAL}` directive to force the application into the main Python interpreter. Note: The repository copy of this config file may be out of sync with production.

### State Persistence (`system_state` Table)
We do not rely on local files (JSON) for state tracking, as they can be lost during container deployments.
*   **Key Data:** `watermark_iso` (Timestamp).
*   **Implementation:** `keepa_deals/db_utils.py` handles the `get_system_state` and `set_system_state` logic.

### Process Management (`start_celery.sh`)
The background processes are orchestrated to be resilient:
*   **Worker:** Executes the tasks (`--concurrency=2` on 1 vCPU VPS to conserve RAM).
*   **Beat:** The scheduler that triggers `smart-ingestor-run` (every 5 min) and `clean_stale_deals` (every 4h).
*   **Zombie Locks:** The `kill_everything_force.sh` script invokes `Diagnostics/kill_redis_safely.py` to perform a "Brain Wipe" (FLUSHALL + SAVE) on Redis during restarts.
*   **Logs:** `celery_worker.log` and `celery_beat.log` are the primary sources for debugging background failures.

### Token Management ("Controlled Deficit")
*   **Strategy:** The system allows the Keepa token balance to dip into the negative (Deficit Spending) to maximize throughput.
*   **Architecture:** **Distributed Token Bucket (Redis-backed)**.
*   **Deficit Protection:** Enforces a hard limit of `MAX_DEFICIT = -180`. If a request would push the balance below this, it is blocked to prevent API lockouts.
*   **Burst Threshold Scaling:** Capped at **50 tokens** for high plans (>= 20/min) and **40 tokens** for lower plans (< 20/min).
*   **Low-Cost Call Buffer:** Allows low-cost calls (cost <= 10) to exit Recharge Mode as soon as token balance reaches **20** tokens.
*   **Lock Release:** If the required wait time exceeds 60 seconds (deep recharge), the `TokenManager` raises a `TokenRechargeError`. The Smart Ingestor catches this and immediately releases the Redis lock, freeing the worker for other tasks.

### Amazon SP-API Integration
*   **Authentication:** Uses "Login with Amazon" (LWA) Access Tokens via `x-amz-access-token`.
*   **No SigV4:** AWS Signature Version 4 (SigV4) signing and IAM credentials are **not required** for this Private App integration.
*   **Environment:** Supports both Sandbox and Production environments, auto-detecting based on the token validity.
