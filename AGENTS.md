# Agent Instructions

> **READ THIS FILE COMPLETELY BEFORE TAKING ANY ACTION.**
> The rules in Sections 1–3 are absolute. Violating them is task failure regardless of how good the resulting code looks.

---

## 1. LOCKED CONFIGURATION VALUES (DO NOT CHANGE WITHOUT EXPLICIT APPROVAL)

The following values are AUTHORITATIVE. Do NOT change them based on assumptions, training data, "best practice," or what you think a newer/better version is. If a change is genuinely needed, STOP and ASK before modifying.

- **xAI model:** `grok-4-fast-reasoning` — NEVER `grok-beta`, `grok-4`, `grok-3`, or any other variant. (Note: xAI's billing console reports this model as `grok-4.3`. That is a billing label, not a model string — do not "correct" the code to match it.)
- **Keepa Epoch:** `datetime(2011, 1, 1)` — NEVER `2000-01-01`. The 11-year offset has caused a critical regression before.
- **SP-API URL:** `https://sellingpartnerapi-na.amazon.com` (Production) — NEVER swap to Sandbox
- **Keepa Query Standard:** `dateRange: 4` MUST be paired with `sortType: 4` (Last Update)
- **Token Manager:** Shared Redis Token Bucket (`keepa_deals/token_manager.py`) — do not bypass
- **MAX_DEFICIT:** `-180` — do not raise without explicit approval
- **Production database:** `deals.db` — NEVER modify or delete during development. Use `DATABASE_URL=dev_deals.db` for development.

If you find yourself "fixing" any of these, you are wrong. Stop.

---

## 2. FORBIDDEN ACTIONS WITHOUT EXPLICIT USER APPROVAL

- Do NOT change model strings, API versions, endpoint URLs, or environment variable names
- Do NOT modify or delete `deals.db` (production database)
- Do NOT modify files in `AgentArbitrage_BeforeGateCheckFeature2/` or any `Archive/` directory
- Do NOT run `find . -delete`, `rm -rf`, or any bulk destructive command
- Do NOT reintroduce fallback pricing logic (Keepa Stats Fallback / Silver Standard) that uses listing averages — see Section 7 "Fallback Data Warning"
- Do NOT remove the Redis "Brain Wipe" cleanup logic from `kill_everything_force.sh`
- Do NOT "improve," refactor, or clean up code outside the scope of the assigned task
- Do NOT mark a task complete if it leaves placeholder logic (`return True`, `candidates.append(all_items)`, etc.) — see Section 6 "Definition of Done"

---

## 3. SCOPE DISCIPLINE

Your task is ONLY what the user explicitly asked. This is the single most important behavioral rule.

- Do not refactor adjacent code
- Do not "fix" things you notice in passing
- Do not change configuration values unless the task is specifically about tuning them
- If you see something concerning outside scope, mention it in your final summary — do NOT act on it
- If a necessary change falls outside the original scope, STOP and ask permission before proceeding

Every change must be directly justifiable by the user's request.

---

## 4. INITIAL CODEBASE EXPLORATION — STRICT FILE READING RULES

At the start of every session, follow these rules exactly. Do not deviate without explicit user permission.

### REQUIRED reading (read in this order, in full):

1. `README.md`
2. `AGENTS.md` (this file)
3. `Documentation/System_State.md`
4. `Documentation/Data_Logic.md`
5. `Documentation/Dashboard_Specification.md`
6. `Documentation/Token_Management_Strategy.md`
7. `Documentation/System_Architecture.md`
8. `Documentation/Feature_Deals_Dashboard.md`
9. `Documentation/Feature_Guided_Learning_Strategies_Brain.md`
10. `Documentation/INFERRED_PRICE_LOGIC.md`
11. The 3 most recent files in `Dev_Logs/` (sorted by date in filename)

### ON-DEMAND reading (read ONLY if the current task explicitly requires it):

- `Documentation/Archive/` — older docs and historical references
- Older `Dev_Logs/` entries beyond the 3 most recent
- `Dev_Logs/Archive/` — only if investigating a regression from that period
- `tests/` — only when writing or debugging tests

### NEVER read (these waste context, cause instability, or contain stale data):

- `*.log` files of any kind, in any directory — including `celery.log` (LEGACY/ABANDONED, massive)
- `xai_cache.json`, `xai_token_state.json` (runtime state)
- `strategies.json`, `agent_brain.json`, `intelligence.json`, `tooltip_cache.json` (large runtime caches)
- `My_Notes/` (personal notes, not project documentation)
- `Diagnostics/` (output reports, not source)
- Any `Archive/` directory contents
- `venv/`, `__pycache__/`, `db_backups/`

### Logging Source of Truth (when logs ARE explicitly required):

- **`celery_worker.log`**: ACTIVE log for background tasks. Use this for troubleshooting.
- **`celery_monitor.log`**: Resiliency logs.
- **`celery.log`**: LEGACY/ABANDONED — DO NOT READ.

### Filesystem inspection rules:

- Use `ls -F` or targeted `ls` on specific directories. Never `ls -R`.
- For any file > 500 KB, use `head -n 100`, `tail -n 100`, or `grep` instead of reading the full file.
- Always check size with `ls -lh` before reading any file you're unsure about.
- NEVER assume a log file is safe to read. Check size first.

### Escape hatch:

If you believe a "never read" or "on-demand" file is necessary to complete the current task, state which file and why before reading it. Do not silently access these files.

---

## 5. ENVIRONMENT AND VERIFICATION PROTOCOL (EVP)

Mandatory for all tasks. Failure to adhere can lead to mission failure due to environmental instability.

### 5.1 Environment Sanity Check (ESC)

Before beginning any code analysis or modification, verify the sandbox environment's integrity:

```bash
touch test_agent_sanity.txt && git add test_agent_sanity.txt && git diff --staged
```

This MUST show a diff indicating a new file. If empty, the environment is faulty — HALT and report. Do not work around a broken environment.

Cleanup: `git reset HEAD test_agent_sanity.txt && rm test_agent_sanity.txt`

### 5.2 Principle of Least Impact Verification (LIV)

Use the most lightweight, targeted verification possible. Do NOT run resource-intensive end-to-end pipelines (like `backfill_deals`) to verify small isolated changes.

- **Backend/API change:** Insert one test row via `sqlite3`, query the endpoint with `curl`.
- **Frontend change:** Use frontend verification tools without populating the entire database.

### 5.3 Database Backup and Restore

Before significant changes:
- `./backup_db.sh` — Creates a timestamped backup
- `./restore_db.sh` — Restores from the most recent backup

---

## 6. THE STABILITY PACT (REGRESSION PREVENTION)

This is your primary directive for keeping hard-won code stable.

### 6.1 Principle of Minimum Scope

Change the absolute minimum code necessary. No unrelated refactoring or "cleanup."

### 6.2 Code Archaeology Before Action

Before modifying existing code:
- Run `git log -p <filepath>` to understand history
- Consult `Dev_Logs/Archive/` ONLY when tracing the origin of a specific feature
- Understand the *intent* before proposing changes

### 6.3 Strict Separation of Code and Configuration

Do not change configuration values (batch sizes, timeouts, thresholds) unless the task is specifically about tuning. If you find hardcoded config during a task, REPORT it and ask before moving it.

### 6.4 Test-Driven Development

- Bug fixes: write a failing test that reproduces the bug FIRST
- New features: write tests defining correct behavior
- Run the ENTIRE test suite before submitting. A failing test is a hard blocker.

**Run it with `./run_tests.sh`, which needs `pip install -r requirements-dev.txt` (pytest).**
The suite runs in **one process**, deliberately. Until September 2026 the script ran each
module in its own `python3 -m unittest` process, which made cross-module interference
structurally invisible: `tests/test_approve_dedup.py` installed `MagicMock`s into
`sys.modules` at import time and never restored them, failing 25 tests in-suite —
including `tests/test_lightweight_upsert_preservation.py`, the §7.12 guard — while
`run_tests.sh` reported everything green.

**The invariant: every test module produces the same result run alone as it does
in-suite.** `tests/conftest.py` enforces it and fails the run, naming the module, if any
test module leaves a mock or a mutated entry behind in `sys.modules`. Scope your mocking
(`unittest.mock.patch.dict(sys.modules, ...)` restores on exit), or use
`tests/_real_module.load()` for a private, unregistered copy of a project module.

*In a fresh sandbox `pip install -r requirements.txt` can fail on blinker
("Cannot uninstall blinker 1.7.0, RECORD file not found"). Use
`pip install --ignore-installed blinker -r requirements.txt`. Without it 26 of 30 test
modules error at import on missing celery/pandas/dotenv, which looks like a broken branch
and is not.*

### 6.5 Explicit Confirmation for Scope Creep

If a necessary change falls outside the original scope, STOP. Present the finding and proposed change. Do not proceed without explicit permission.

### 6.6 Definition of Done — The Logic Check

**WARNING: The "Infrastructure vs. Logic" Trap.** Tasks often split into:
1. **Infrastructure** — scaffolding (loops, function calls, integrations)
2. **Logic** — the actual decision-making (filtering, pricing, rejection)

**A task is NOT DONE until both are complete.**

- NEVER leave placeholders like `candidates.append(all_items)` or `return True` with intent to "refine later"
- If infrastructure must merge before logic is ready, the feature MUST be DISABLED by default (feature flag or commented out)
- "Zombie Features" (infrastructure without logic) consume resources but provide no value — worse than not having the feature at all

**Verification step:** Before marking complete, ask: *"Does this code actually make decisions, or is it just moving data?"*

---

## 7. TECHNICAL AND HISTORICAL NOTES

Consult these notes before working on related parts of the codebase.

### 7.1 Fallback Data Warning (CRITICAL — Jan & Mar 2026)

**Do NOT use unverified fallback data to fill missing fields or estimate prices.**

Previous attempts to "solve" data gaps using fallback values (e.g., Keepa Stats listing averages like `avg90` or `avg365` when inferred sales were sparse) resulted in artificially elevated list prices and "fake profits."

- **Principle:** If the primary data source (confirmed true inferred sales via drops vs. offers) is missing, REJECT the deal (return `None` or `-1`). Incorrect guesses based on listing prices lead to wildly inaccurate margins and damage subscriber trust.
- **March 2026 Addendum:** The "Keepa Stats Fallback" (Silver Standard) logic was explicitly removed from `stable_calculations.py`. **Do not reintroduce fallback logic that uses listing prices to inflate deal volume.** If 0 inferred sales, the deal MUST be rejected.
- **September 2026 Addendum:** That removal covered only `stable_calculations.py`. A second fallback survived in `new_analytics.py` on the `1yr. Avg.` path — `max(stats.avg365[2, 19, 20, 21, 22])`, the most expensive of five listing-average condition tiers — and was removed on 2026-09-11 (audit B-6). **`1yr. Avg.` and `List at` may now come ONLY from true inferred sales.** No listing average, no Amazon price, no Keepa list price, no default, no max or min across condition tiers, on any path. If you are about to add one, you are wrong. Stop.
  - Note the consequence: `List at` uses a 3-year window and `1yr. Avg.` a 1-year one, so a valid `List_at` alongside a NULL `1yr_Avg` is now a legitimate state. `1yr_Avg IS NULL` is **not** a data-damage fingerprint.

### 7.2 Role-Based Access Control (RBAC)

- **User Roles:** `admin` and `user`
- **Admin Only:** `/deals`, `/guided_learning`, `/strategies`, `/intelligence`
- **User Accessible:** `/dashboard`, `/settings`
- **Mechanism:** `wsgi_handler.py` checks `session['role']` on restricted routes; redirects unauthorized users to dashboard
- **Navigation:** Frontend templates conditionally render nav links based on role

### 7.3 Timestamp Handling (from task ~June 24-25, 2025)

Goal: reflect the most recent relevant event accurately, aligned with user expectations from Keepa.com.

**For `last_update`:**
Most recent time any significant data was updated by Keepa. Take MAX valid timestamp from:
1. `product_data['products'][0]['lastUpdate']` (general product data, /product endpoint)
2. `deal_object.get('lastUpdate')` (general deal data, /deal endpoint)
3. `product_data.get('stats', {}).get('lastOffersUpdate')` (offers refresh, /product stats)

**Only source 2 is reachable in production (September 2026).** `last_update` is invoked
through `FUNCTION_LIST`, and the generic loop in `processing.py` calls every field
function as `func(product_data)` — **one positional argument**. That binds the merged
product dict to `deal_object` and leaves the function's own `product_data` parameter at
its `None` default, so sources 1 and 3, which both read that parameter, never run. Source
2 reads the single argument, and `smart_ingestor.run()` does `product_data.update(deal)`
before processing, so it resolves to the **deal object's** `lastUpdate`. That is the
value stored today. A three-source MAX would need a different call shape, which is a
behavioural change, not a bug fix.

**The whole column was NULL before September 2026.** `logger_param` had no default, so
`func(product_data)` raised `TypeError` on every heavy-path deal, `_process_single_deal`
swallowed it per field, and the upsert bound the missing key as `NULL`. The
`@retry(stop_max_attempt_number=3, wait_fixed=5000)` then on the function turned that
permanent error into **two 5-second sleeps per newly discovered deal**.

**Rule for every `FUNCTION_LIST` entry:** it must be callable as `func(product_data)`,
and it must not carry a retry decorator unless it actually performs I/O. These functions
read in-memory dicts; a retry on them cannot fix anything and costs `wait_fixed` per
attempt on the heavy path. Guarded by `tests/test_field_mappings_call_contract.py`.

**For `last_price_change` (Used items, excluding 'Acceptable'):**

1. **Primary (`product_data.csv`):** Check 'USED' (`csv[2]`), 'USED_LIKE_NEW' (`csv[6]`), 'USED_VERY_GOOD' (`csv[7]`), 'USED_GOOD' (`csv[8]`). Select most recent valid timestamp.
2. **Fallback (`deal_object.currentSince`):** Check `currentSince[2]` (Used), `[19]` (Like-New), `[20]` (Very-Good), `[21]` (Good). If `current[14]` indicates Buy Box is 'Used', also check `currentSince[32]` (buyBoxUsedPrice). Select most recent.

**General Conversion:**
Keepa minute timestamps → datetime via `KEEPA_EPOCH = datetime(2011, 1, 1)`, localize naive UTC → aware UTC (`timezone('UTC').localize(dt)`) → 'America/Toronto' (`astimezone(TORONTO_TZ)`), format `'%Y-%m-%d %H:%M:%S'`. Timestamps ≤ 100000 are invalid/too old.

**The "Keepa Epoch Bug" (Jan 2026):**
A critical regression occurred when the system used `2000-01-01` instead of `2011-01-01`. The 11-year offset caused fresh 2026 data to be seen as 2015 data ("Ancient Data"), causing the ingestion pipeline to reject everything. **Always verify the epoch is 2011.**

### 7.4 Circular Dependencies & Module Structure

- **`keepa_deals/new_analytics.py`**: Houses downstream analytical logic (trend calculations, offer count averages) to prevent circular imports between `processing.py`, `stable_calculations.py`, `stable_products.py`.
- **Rule:** New metrics depending on core calculations (like inferred sales) but used by the main processing loop go in `new_analytics.py` — do NOT modify core stable modules.

### 7.5 Token Management & Rate Limiting

- **Blocking Wait Strategy:** Prevents 429 errors. API wrapper functions accept a `token_manager` argument. Calling `token_manager.request_permission_for_call()` sleeps the thread until tokens are available rather than failing.
- **Rule:** New API calls in high-volume loops MUST integrate with the `TokenManager`.

### 7.6 UI & SVG Standards

- **Icons:** Navigation SVGs have `viewBox` reset to content bounding box (no internal padding), strictly **20px** height in CSS (`static/global.css`)
- **Header:** `.main-header` strictly **134px**. Altering breaks sticky filter alignment.
- **Sticky Headers:** Dashboard table relies on `top` offsets (177px, 233px, 264px, 289px) hardcoded to Main Header + Filter Panel heights. `.filter-panel` MUST have `margin-bottom: 0px`.
- **Table Width:** `#deals-table` strict **1200px** max-width. To fit 15+ columns:
  - Large financial values (Profit, All_in_Cost): drop decimals (`minimumFractionDigits: 0`)
  - Text-heavy columns (`Detailed_Seasonality`): strict `max-width: 105px` with `text-overflow: ellipsis`
  - Cell padding: `padding: 0 8px`. Don't pad top/bottom of sortable headers.

### 7.7 Keepa Query Standards

- **Date Range:** `dateRange: 4` (All Combined) is permissible — captures max 3-year history for AI analysis
- **Sorting:** With `dateRange: 4`, MUST use `sortType: 4` (Last Update) to ensure fresh data, not stale 2015 deals

### 7.8 Critical Fixes & Stability (Feb 2026)

- **Token Starvation & Zombie Locks:** Shared Redis Token Bucket (`keepa_deals/token_manager.py`) coordinates API usage. Kill script (`kill_everything_force.sh`) performs a "Brain Wipe" (FLUSHALL + SAVE) on Redis to prevent persistent locks after a crash. **Do not remove this cleanup logic.**
- **Ghost Deals:** MFN offers with unknown shipping (`-1`) are strictly rejected. Do not "guess" shipping costs for MFN sellers.
- **Seller Name Preservation:** "Lightweight Updates" lack seller names; system uses `Seller ID` to preserve existing human-readable names. If you modify `processing.py`, ensure this logic remains intact.
- **Zero Profit & Missing Data Persistence:** Deals with `Profit <= 0` or missing `List at` are PERSISTED (not rejected) to prevent infinite re-fetch loops. Filtered from Dashboard.
- **Sparse Sales Rescue:** Median of inferred sales (1-2 events) used as a "Sparse Rescue" price — represents true inferred sales. Skips XAI checks to prevent false negatives from missing context.
- **Deficit Protection:** `MAX_DEFICIT = -180` enforced to prevent API lockouts.
- **Stale Deal Rescue:** `rescue_stale_deals` in `keepa_deals/smart_ingestor.py` proactively refreshes deals older than 48 hours to prevent Janitor deletion (72h limit).
- **Amazon Ceiling Check:** In `keepa_deals/processing.py` lightweight updates, if `List at` > 90% of current Amazon New Price, clamp to that ceiling. Prevents "fake profit" when market drops.

### 7.12 DB Column Naming Contract (September 2026) — CRITICAL

The deals table is named with **sanitized** column names (`List_at`, `1yr_Avg`, `Sales_Rank_Current`, `All_in_Cost`). The field functions return values under **display** names from `headers.json` (`List at`, `Sales Rank - Current`, `All-in Cost`). Mixing the two in one row dictionary destroyed data in production.

- **`_process_lightweight_update` rows are keyed by SANITIZED names.** They come from `dict(sqlite3.Row)` off `SELECT * FROM deals`. Every field-function result merged into such a row MUST go through `_merge_db_keyed`. Never `row_data.update(some_field_function(...))` directly, and never write a literal display name into that row.
- **No-data sentinels (`-`, `''`, `N/A`, `None`) never overwrite a stored value.** Field functions report failure in band, under their normal key, so a caller that writes unconditionally replaces a good stored value with nothing. The row being merged into is an existing DB row, so the stored value is always the better answer. `_merge_db_keyed` applies the `_is_no_data` guard for every value it merges; the one write in `_process_lightweight_update` that bypasses it, the explicit `Drops` mapping, must apply the guard itself. Do NOT rewrite that check as a falsiness test: `0` and `'0'` are real readings and must overwrite. See "LIGHTWEIGHT PRESERVATION RULE" in `Data_Logic.md`.
- **`_process_single_deal` rows are keyed by DISPLAY names.** That is correct for the heavy path — do not "align" it with the light path. Because `smart_ingestor.run()` upserts heavy and light rows in the **same batch**, heavy rows are re-keyed with `to_db_keys` right after `clean_numeric_values` and before they join `rows_to_upsert`. Removing that call silently NULLs 221 columns on every newly discovered deal.
- **Both Smart Ingestor upserts go through `upsert_deal_rows`** (`keepa_deals/db_utils.py`). Do not hand-roll the deals upsert SQL at a call site; the helper derives its columns from `headers.json` via `sanitize_col_name`, the same transform that CREATEs the table.
- **What went wrong:** the main Light Update upsert read display names off a sanitized-keyed row, resolving 215 of 246 columns to `None` and writing them as `NULL` every cycle — `List_at`, `Price_Now`, `1yr_Avg`, `Deal_Trust` included. Rows vanish silently from the dashboard (`/api/deals` filters `List_at IS NOT NULL`); the grid does not empty, so the failure is invisible. The Stale Rescue had the mirror defect and wrote stale rank/offers/cost back alongside a Profit computed from the fresh cost.
- **Unrecoverable without tokens:** `recalculator.py` cannot rebuild `List_at`. It derives from `infer_sale_events`, which needs Keepa `csv` history that `deals.db` never stores. Worse, the recalculator writes `Profit`/`Margin`/`Total_AMZ_fees` as NULL for any row where `List_at` is NULL — running it on damaged rows deepens the loss. Recovery is a heavy re-fetch at ~20 tokens/ASIN.
- **Guarded by:** `tests/test_lightweight_upsert_preservation.py`. It builds the schema from `headers.json` and calls the production upsert, so it cannot be satisfied by a fixture that encodes the wrong convention. If you change key handling in `processing.py` or either upsert site, this test must stay green.

### 7.9 Recent Fixes (March 2026)

- **Self-Aware Mentor & Tooltips:** `keepa_deals/platform_knowledge.py` dynamically loads documentation into AI context. Instant speech-bubble tooltips on Deals Dashboard headers/filters.
  - **Constraint:** `?` icon removed from column headers (violated 1200px limit). Triggers (`.ai-tooltip-trigger`) applied to text/labels directly. Server-side JSON cache (`tooltip_cache.json`) prevents latency and token waste.
- **Astronomical Profits Fix:** Hard ceiling in `keepa_deals/stable_calculations.py` rejects `List At` > $1,500. The > 3.0 ratio check (Suspiciously High Markup) now applies to ALL price sources. AI Prompt updated to reject non-textbook used prices > $500.
- **Database Clearing Script:** `./clear_deals.sh` non-interactively clears `deals` and `user_restrictions` tables without wiping the entire DB or prompting — ideal for pre-deployment cleanup.
- **FBA Inventory Sync:** Switched to `GET_FBA_MYI_ALL_INVENTORY_DATA` (resolved FATAL errors from unsuppressed report). Logic includes Inbound inventory (Working, Shipped, Receiving).
- **Credential Management:** Backend and diagnostics strictly prioritize Database (`deals.db`) lookup for Seller ID and Refresh Tokens. `.env` reserved for global app config (Client ID/Secret) only.
- **Dynamic ROI & All-in Cost:** `All-in Cost` strictly excludes Amazon fees (deducted separately for `Profit`). `ROI = (Profit / All_in_Cost) * 100`, dynamically calculated, NOT stored. Warn against updating non-existent DB columns (like `Total AMZ fees`) via raw SQL.
- **Smart Ingestor Batch Size:** Default **50** (High Rate), reduces to **20** (Low < 20/min) and **1** (Critically Low < 10/min) to fit within 40-token burst window without livelock.
- **Stall Watchdog:** `Diagnostics/watchdog_stall_detector.py` identifies stuck workers (Tokens > 290 + no Heartbeat for 15 mins).

### 7.10 Recent Fixes (May 2026)

- **Agent's Choice (Prime Picks) Filter Fix:** Resolved a 504 Gateway Timeout issue caused by sending overly large payloads to the xAI API. The solution implements an async **Two-Pass Pipeline** in `keepa_deals/prime_picks_task.py`:
  - **Pass 1 (Smart Floor):** SQL/math filtering to score and find top candidates.
  - **Pass 2 (xAI Mastermind):** Evaluates top candidates using `grok-4-fast-reasoning`. Employs **Tiered Strategy Injection** to limit the injected rules to a strict cap of 'High' confidence strategies from core categories, dynamically matching relevant contexts to reduce payload size.
  - **Caching:** Successful evaluation results are cached atomically in the new `prime_picks` database table, allowing instant UI reads without blocking the web thread.
  - **Graceful Fallback:** If Pass 2 fails (e.g., due to xAI API errors), the system explicitly skips updating the cache, preserving the last known valid run instead of displaying an empty list or unfiltered candidates.

### 7.11 Recent Fixes (May 2026 - Part 2)

- **Prime Picks Refinements:**
  - **Pass 1 Offer Trend:** Updated the deduplication comparison to use the `365-day average` instead of the 30-day average, resolving issues where missing short-term data neutralized the filter.
  - **Pass 1 Year-Round Velocity Cap:** Introduced a hard cap (Rank > 2,000,000) for explicitly non-seasonal "Year-round" items to structurally drop weak deals while exempting seasonal inventory.
  - **Pass 2 Prompt Correction:** Added a `SEASONAL HIGH-RANK CORRECTION` block to the xAI prompt, instructing the model not to reject valid seasonal deals based solely on high off-season ranks.
- **AI Mentorship & Strategy Alignment:**
  - **Shared Strategic Corrections:** Extracted `TEXTBOOK COUNTERFEIT RISK CORRECTION` and `SEASONAL HIGH-RANK CORRECTION` into a shared module-level constant (`STRATEGIC_CORRECTIONS`) in `keepa_deals/ava_advisor.py`. This ensures consistency across Mentor Advice (Ava), Mentor Chat, and Pass 2 evaluations.
  - **Dual Strategy Framing:** Updated the `STRATEGIC_CORRECTIONS` block to evaluate candidates against a dual-strategy framework (high-velocity flips vs. seasonal holds). This removes the AI's bias toward treating all inventory strictly as high-velocity replens.
- **Database Connections & Deadlocks:**
  - **Centralized Helper:** Replaced direct `sqlite3.connect` calls across the codebase with the `get_db_connection` helper from `keepa_deals.db_utils` to enforce `busy_timeout=5000` and `journal_mode=WAL` uniformly.
  - **Context Manager Requirement:** All assignments (`conn = get_db_connection(...)`) MUST be used within a `with` context block (or explicitly closed in a `finally` block). Unclosed connections leak and prevent SQLite from executing `PRAGMA` statements on new connections, leading to severe lock contention.
  - **`mod_wsgi` C-Extension Deadlocks:** The centralized database helper, utilizing the `sqlite3` C-extension, triggered WSGI hangs in production when running within isolated sub-interpreters. The live Apache virtual host config (`agentarbitrage.conf`) **must** include the `WSGIApplicationGroup %{GLOBAL}` directive to force execution in the main interpreter.
- **Tracking UI & Unified Pagination:**
  - Pagination logic is centralized in `static/js/pagination.js`. Tracking pages implement client-side sorting and hyperlink generation for ASINs/SKUs/Order IDs.
  - CSV features on the Active Inventory tab are demoted under a bulk edit link to minimize clutter.