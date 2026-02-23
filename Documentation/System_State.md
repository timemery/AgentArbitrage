# System State & Architecture Snapshot
*Active Source of Truth for Agent Arbitrage*

## 1. Core Architecture
- **Application:** Flask web server (`wsgi_handler.py`) serving a Jinja2 frontend (`templates/`).
- **Background Tasks:** Celery workers (`celery_app.py`) managing data ingestion and maintenance.
- **Database:** SQLite (`deals.db`). Use `db_utils.py` for schema interactions.
- **Environment:** Requires `.env` with API keys (Keepa, xAI, SP-API).
- **Logging:** `celery_worker.log` is the active log. `celery.log` is legacy/abandoned; do not read it.

## 2. Role-Based Access Control (RBAC)
- **Admin Only:** `/deals` (Config), `/guided_learning`, `/strategies`, `/intelligence`.
- **User Accessible:** `/dashboard`, `/settings`.
- **Mechanism:** `session['role']` checked in `wsgi_handler.py`.

## 3. Data Pipeline & Logic
### Pricing & Inferred Sales
- **"List at" Price:** Derived from Peak Season history (Mode).
    -   **Fallback:** If Inferred Sales < 3, falls back to `Used/Collectible - 365d Avg` (Silver Standard). If stats missing, uses **Median of Inferred Sales** (Sparse Rescue).
    - **Validation:** **ALL** prices (including fallbacks) must pass the **Amazon Ceiling Check** (90% of lowest New price).
    -   **XAI Check:** The **XAI Reasonableness Check** is applied to standard prices but is **SKIPPED** for "Keepa Stats Fallback" and "Sparse Rescue" prices to prevent false rejections.
- **"Expected Trough" Price:** Median price of the identified trough month.
- **Sales Inference:** Search window is **240 hours (10 days)**.
    - **XAI Rescue (Hidden Sales):** If the standard algorithm finds 0 confirmed sales or no offer drops, the system calls **xAI** to identify "Hidden Sales" (rank drops without offer drops), rescuing potentially valid deals.
    - **Sparse Data:** Logic includes a **30-day lookahead** for rank drops to infer sales even when data points are sparse (e.g., slow movers).
- **Extended Metrics:** 180-day and 365-day trend analysis for Offer Counts and Sales Rank drops.

### Smart Ingestor & Maintenance
- **Smart Ingestor (v3.0):** The unified entry point for all deal ingestion (`keepa_deals.smart_ingestor`). Replaces legacy `backfiller` and `simple_task`.
    - **Logic:** Explicitly sorts Keepa responses by `lastUpdate` (descending) to ensure strictly ordered processing.
    - **Watermark:** Implements a "Ratchet" mechanism (advances even if deals are rejected) and tolerates up to **24 hours** of future clock skew before clamping.
    -   **Data Persistence Strategy (formerly Zombie Defense):** The aggressive re-fetching logic for 'Zombie' deals (missing critical data like `List at`) was found to cause infinite loops and token waste. It has been replaced by a **Persistence Strategy** where deals with missing data are saved and updated via standard 'Lightweight Updates', allowing for gradual data repair without system strain.
    - **Throughput:** Uses a **Decoupled Batching Strategy**:
        - **Peek / Light Update:** Batch size **50** (reduces to **20** if refill rate < 20/min, and **1** if < 10/min).
        - **Peek Filter:** `salesRankDrops365` threshold reduced to **1** (from 4) to capture "Silver Standard" deals.
        - **Commit (Heavy Analysis):** Batch size **5** to prevent deficit shock.
    - **Deficit Protection:** Enforces `MAX_DEFICIT = -180` to prevent API lockouts.
    - **Lock Release:** Raises `TokenRechargeError` during long waits (> 60s) to release the Redis lock and free the worker.
- **Janitor:** Deletes deals older than **72 hours**.
- **Tokens:** `TokenManager` uses a "Burst Mode" strategy:
    - **Threshold:** `MIN_TOKEN_THRESHOLD` reduced to **1** to aggressively use the negative deficit allowance.
    - **Recharge Mode:** If tokens run out, system pauses until it reaches the **Burst Threshold** (40 for slow connections < 10/min, 280 for fast). This prevents "flapping" and starvation loops.
    - **Optimization:** `should_skip_sync()` checks local estimates before API calls, preventing token drain during deep deficits.
    - **Shared State:** Uses Redis (`keepa_tokens_left`) to coordinate quotas across all workers.

## 4. Dashboard & UI
- **Notifications:** "New Deals" count is filter-aware (matches active filters).
- **Filtering:**
  - Default view (`Margin >= 0`) excludes `NULL` margins.
  - "Reset" button sets all sliders to 0 ("Any"), which explicitly removes the filter from the query.
  - **New Filters:** "Hide Gated" (excludes restricted items) and "Hide AMZ Offers" (excludes items sold by Amazon).
- **Columns:**
  - **Drops:** Sales Rank drops in last 30 days.
  - **Offers:** Trend arrows (↘ Green/Falling, ↗ Red/Rising) vs 30-day average.
  - **AMZ:** Warning icon (⚠️) right-aligned in "Offers" column if Amazon is currently selling.
- **Ava Advice:** Overlay feature using `grok-4-fast-reasoning` to provide actionable analysis.
- **Mentor Chat:** Persistent overlay (505x540px) accessible from nav. Features 4 personas (Olyvia, Joel, Evelyn, Errol) synchronized via `localStorage`.
- **Refresh Logic:** Manual "Refresh Deals" button only reloads the grid; it no longer triggers the "Janitor" cleanup process (as of Jan 2026). The admin-side "Manual Data Refresh" (recalculation) feature was also removed in Feb 2026.
- **Navigation:**
  - **Structure:** Divided into three sections: Left (Logo, Dashboard, Tracking), Center (Admin Links), and Right (Mentor, Settings, Logout).
  - **Header Height:** Strictly fixed at **134px** to support the sticky filter panel layout.
  - **Icons:** SVG icons are optimized to **20px** height with zero internal padding.

## 5. Strategy Database
- **Format:** Structured JSON (`id`, `category`, `trigger`, `advice`, `confidence`).
- **Legacy Support:** System supports "Hybrid" mode (Legacy Strings + New Objects) for backward compatibility.
- **Migration:** `migrate_strategies.py` converts legacy text to structured JSON.

## 6. Known Constraints & Hard Rules
- **Formatting:** `format_currency` handles string inputs defensively.
- **Logs:** Do not read full `celery.log`.
- **Context:** `Dev_Logs/Archive/*.md` files are historical archives. This file is the current reference.
- **Batch Size:** Decoupled (50 for Peek, 1/5 for Critically Low Rate/Commit) to maximize deficit spending efficiency while preventing shock.
- **Redis Lock:** `smart_ingestor_lock` is the primary mutex. Timeout 30 minutes.
- **Redis Cleanup:** `kill_everything_force.sh` performs a full wipe (FLUSHALL). `deploy_update.sh` adds surgical lock removal as a safety net.
- **Janitor Grace Period:** **72 Hours**. Do not lower (causes data loss).

## Profit & Inventory Tracking (Feb 2026 Update)
- **FBA Data Source:** Now uses `GET_FBA_MYI_ALL_INVENTORY_DATA` to ensure comprehensive coverage and avoid FATAL errors.
- **Inventory Definition:** "Active" quantity = `afn-fulfillable-quantity` + Inbound (`working`, `shipped`, `receiving`).
- **Credential Architecture:**
    - **User Credentials (Seller ID, Refresh Token):** Stored in `deals.db` (`user_credentials` table). Loaded via `db_utils.get_all_user_credentials()`.
    - **App Credentials (Client ID, Secret):** Stored in `.env` (Global).
    - **Diagnostics:** Tools like `check_inventory_permissions.py` and `inject_credentials.py` now support this hybrid model and include interactive fallbacks.
- **Environment:** Production SP-API URL is hardcoded to prevent Sandbox leakage.
