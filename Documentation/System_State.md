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
- **"List at" Price:** Derived from Peak Season history or `monthlySold` fallback.
- **"Expected Trough" Price:** Median price of the identified trough month.
- **Safety Ceiling:** Capped at 90% of the lowest Amazon "New" price (Min of Current, 180d, 365d).
- **Validation:** Prices checked by xAI (`ava_advisor.py`) for reasonableness (Page Count, Binding, etc.).
- **Sales Inference:** Search window is **240 hours (10 days)** to capture "Near Miss" sales events.
- **Extended Metrics:** 180-day and 365-day trend analysis for Offer Counts and Sales Rank drops.

### Backfill & Maintenance
- **Backfiller:** Runs continuous delta-sync. Uses "Mark and Sweep" to update `last_seen_utc`.
- **Janitor:** Deletes deals older than **72 hours** (`grace_period_hours`).
- **Configuration:** The "Artificial Backfill Limiter" logic remains in `backfiller.py` but is inactive by default.
- **Tokens:** `TokenManager` uses a "Controlled Deficit" strategy (Threshold reduced to 20). Implements "Recharge Mode" (pauses if tokens < 20 & rate < 10/min until full) to prevent starvation.
- **Concurrency:** Backfiller and Upserter run concurrently. Upserter frequency reduced to 15 mins. Both tasks dynamically reduce batch size to 1 if refill rate < 20/min.

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

## 6. Known Constraints & Hard Rules
- **Formatting:** `format_currency` handles string inputs defensively.
- **Logs:** Do not read full `celery.log`.
- **Context:** `Dev_Logs/Archive/*.md` files are historical archives. This file is the current reference.
- **Backfill Chunk Size:** Default **20**, but dynamically reduces to **1** if Keepa refill rate is < 20/min to prevent starvation.
- **Redis Lock:** `backfill_deals_lock` timeout reduced to **1 hour (3600s)** to prevent zombie locks.
- **Redis Cleanup:** `kill_everything_force.sh` performs a full wipe (FLUSHALL). `deploy_update.sh` adds surgical lock removal as a safety net.
- **Janitor Grace Period:** **72 Hours**. Do not lower (causes data loss).
