# System State & Architecture Snapshot
*Active Source of Truth for Agent Arbitrage*

## 1. Core Architecture
- **Application:** Flask web server (`wsgi_handler.py`) serving a Jinja2 frontend (`templates/`).
- **Background Tasks:** Celery workers (`celery_app.py`) managing data ingestion and maintenance.
- **Database:** SQLite (`deals.db`). Use `db_utils.py` for schema interactions.
- **Environment:** Requires `.env` with API keys (Keepa, xAI, SP-API).
- **Logging:** `celery.log` is massive; use `tail`/`grep` only.

## 2. Role-Based Access Control (RBAC)
- **Admin Only:** `/deals` (Config), `/guided_learning`, `/strategies`, `/agent_brain`.
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
- **Tokens:** `TokenManager` uses a "Controlled Deficit" strategy (allows dips to -50, refills to +5).
- **Concurrency:** Backfiller and Upserter (`simple_task.py`) run concurrently. Upserter requires 20 token buffer.

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
- **Refresh Logic:** Manual "Refresh Deals" button only reloads the grid; it no longer triggers the "Janitor" cleanup process (as of Jan 2026).

## 5. Strategy Database
- **Format:** Structured JSON (`id`, `category`, `trigger`, `advice`, `confidence`).
- **Legacy Support:** System supports "Hybrid" mode (Legacy Strings + New Objects) for backward compatibility.
- **Migration:** `migrate_strategies.py` converts legacy text to structured JSON.

## 6. Known Constraints & Hard Rules
- **Formatting:** `format_currency` handles string inputs defensively.
- **Logs:** Do not read full `celery.log`.
- **Context:** `Dev_Logs/Archive/*.md` files are historical archives. This file is the current reference.
- **Backfill Chunk Size:** Must remain **20** (`DEALS_PER_CHUNK`). Increasing causes Token Starvation.
- **Redis Lock:** `backfill_deals_lock` has a **10-day timeout** to support long-running tasks.
- **Janitor Grace Period:** **72 Hours**. Do not lower (causes data loss).
