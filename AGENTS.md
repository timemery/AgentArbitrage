# Agent Instructions

## Database Management (CRITICAL)

**Production Data:** The `deals.db` file is the production database and should NOT be modified or deleted during development. Your top priority is to protect this file.

**Development Database:** To work on the application, use a separate database file for development. This can be configured by setting the `DATABASE_URL` environment variable to the path of your development database file (e.g., `export DATABASE_URL=dev_deals.db`). All development and testing must be done against this separate database.

**Backup and Restore:** Before making significant changes, it is wise to create a backup. Use the following scripts to manage the production database:
- `./backup_db.sh`: Creates a timestamped backup of the database.
- `./restore_db.sh`: Restores the database from the most recent backup.

---

### Standard Operating Procedures (SOP) for System Stability

To ensure the stability and performance of the development environment, the following procedures must be followed:

1. **Handling Large Files (especially logs):**

   *   **NEVER** read an entire file if it is known or suspected to be large (e.g., > 500 KB). Large JSON or log files will immediately flood the context window and cause instability.
   *   **ALWAYS** use targeted commands to inspect large files.
       *   To view the end of a file: `tail -n 100 <filepath>`
       *   To view the beginning of a file: `head -n 100 <filepath>`
       *   To search for specific patterns, errors, or keywords: `grep "my search pattern" <filepath>`
   *   If you need to understand the general structure of a large log or data file, use a combination of `head`, `tail`, and `grep` to build a picture without loading the entire file into memory.
   *   **NEVER** assume a log file (like `celery.log`) is safe to read. Always check its size with `ls -lh` first.

2. **Initial Codebase Exploration ("Filesystem Tour"):**

   *   At the beginning of any new task, perform a "filesystem tour" to understand the layout and structure of the codebase.
   *   Use `ls -F` (non-recursive) or targeted `ls` commands on key directories (e.g., `ls -F keepa_deals/`) to list files. **AVOID** `ls -R` as it generates excessive output.
   *   **DO NOT READ** the following large system state files:
       - `xai_cache.json`
       - `strategies.json`
       - `agent_brain.json`
       - `strategies_structured.json`
   *   **READ** `README.md`, this `AGENTS.md` file, and `Documentation/System_State.md` in full.
   *   **READ** the 3-5 most recent logs in `Dev_Logs/` to understand the latest changes.
   *   **DO NOT** read old logs in `Dev_Logs/Archive/` unless specifically investigating a regression related to that time period. `Documentation/System_State.md` is your primary source of truth.
   *   This initial exploration provides essential context, helps locate relevant code modules, and prevents unnecessary file reading later in the task. Adhering to this practice is mandatory for efficient and stable operation.

3. ### Environment and Verification Protocol (EVP)

   To ensure stability and efficiency, the following protocol is mandatory for all tasks. Failure to adhere to these steps can lead to mission failure due to environmental instability.

   1. **Environment Sanity Check (ESC):** Before beginning any code analysis or modification, you MUST verify the sandbox environment's integrity. Perform a simple file creation and version control check: `touch test_agent_sanity.txt && git add test_agent_sanity.txt && git diff --staged`. This command MUST show a diff indicating a new file. If it returns empty, the environment is faulty. You MUST halt immediately and report the environment as unstable. Afterwards, clean up with `git reset HEAD test_agent_sanity.txt && rm test_agent_sanity.txt`. Do not attempt to work around a broken environment.
   2. **Principle of Least Impact Verification (LIV):** Your verification plan MUST use the most lightweight and targeted method possible. Do not run resource-intensive, end-to-end data pipelines (like `backfill_deals`) to verify small, isolated changes.
      - **Example for a backend/API change:** Manually insert a single test row into the database using `sqlite3` and query the specific API endpoint with `curl`.
      - **Example for a frontend change:** Use the provided frontend verification tools without populating the entire database. This principle is critical to minimizing resource usage and avoiding sandbox failures.

---

## The Stability Pact: A Standard Operating Procedure for Preventing Regression

To prevent regressions and ensure that "hard-won" code remains stable, I will adhere to the following principles for every task. This pact is my primary directive.

**1. Principle of Minimum Scope:**

*   I will only change the absolute minimum code necessary to complete the current task.
*   I will not perform unrelated refactoring or "cleanup" of files I am not explicitly tasked to work on.
*   Every change I make must be directly justifiable by the user's request.

**2. "Code Archaeology" Before Action:**

*   Before modifying any existing code, I must first understand its history and purpose.
*   I will use `git log -p <filepath>` to review the recent history of the file to understand why it is in its current state.
*   I will consult the `Dev_Logs/Archive/` directory ONLY if I need to trace the origin of a specific feature.
*   My goal is to understand the *intent* behind the existing code before I propose a change.

**3. Strict Separation of Code and Configuration:**

*   I will not change configuration values (e.g., batch sizes, timeouts, thresholds) unless the task is specifically about tuning those parameters.
*   Such values should be stored in dedicated internal configuration files (e.g., `app_config.py`).
*   If I find hardcoded configuration values during a task, I will report them to you and ask for permission before moving them to a dedicated file.

**4. Test-Driven Development as a Rule:**

*   For all future bug fixes, my first step will be to write a new, failing test that precisely reproduces the bug.
*   For all new features, I will write tests that define the feature's correct behavior.
*   I will run the *entire* test suite before submitting any change. A failing test is a hard blocker. This is our primary automated guard against regression.

**5. Explicit Confirmation for Scope Creep:**

*   If, during a task, I identify a necessary change that falls outside the original scope (e.g., a required refactor in an unrelated file), I will **stop**.
*   I will present my finding and the proposed change to you and will not proceed until I receive your explicit permission.

---

## Technical and Historical Notes

This section contains valuable context and learnings from previous development tasks. Consult these notes before working on related parts of the codebase.

### Fallback Data Warning (CRITICAL - Jan 2026)
**Do NOT use unverified fallback data to fill missing fields.**
Previous attempts to "solve" data gaps by using fallback values (e.g., using `monthlySold` velocity to justify using a stale `avg90` Used price) resulted in massive rejection rates and dwindling deal counts.
-   **Principle:** If the primary data source (e.g., confirmed inferred sales) is missing, it is better to return `None` (and reject the deal) than to guess. Incorrect guesses lead to "Zombie Listings" passing initial checks but failing downstream validation (AI checks), wasting resources and obscuring real issues.

### Role-Based Access Control (RBAC)
-   **User Roles:** The system distinguishes between `admin` and `user` roles.
-   **Access Enforcement:**
    -   **Admin Only:** `/deals`, `/guided_learning`, `/strategies`, `/agent_brain`.
    -   **User Accessible:** `/dashboard`, `/settings`.
    -   **Mechanism:** `wsgi_handler.py` checks `session['role']` on restricted routes and redirects unauthorized users to the dashboard.
-   **Navigation:** Frontend templates conditionally render navigation links based on the user's role.

### Timestamp Handling Notes (from Task starting ~June 24-25, 2025)

When working with timestamp fields like 'last update' and 'last price change', the goal is to reflect the most recent relevant event as accurately as possible, aligning with user expectations from observing Keepa.com.

**For 'last_update':**
This field should represent the most recent time any significant data for the product/deal was updated by Keepa. It considers:
1.  `product_data['products'][0]['lastUpdate']` (general product data update from /product endpoint).
2.  `deal_object.get('lastUpdate')` (general deal data update from /deal endpoint).
3.  `product_data.get('stats', {}).get('lastOffersUpdate')` (when offers were last refreshed from /product endpoint stats).
The function should take the maximum valid (recent) timestamp from these three sources.

**For 'last_price_change' (specifically for Used items, excluding 'Acceptable'):**
This field aims to find the most recent price change for relevant used conditions.
1.  **Primary Source (`product_data.csv`):** Check historical data for 'USED' (`csv[2]`), 'USED_LIKE_NEW' (`csv[6]`), 'USED_VERY_GOOD' (`csv[7]`), and 'USED_GOOD' (`csv[8]`). Select the most recent valid timestamp from these.
2.  **Fallback Source (`deal_object.currentSince`):** If CSV data is insufficient, check `currentSince[2]` (Used), `currentSince[19]` (Used-LikeNew), `currentSince[20]` (Used-VeryGood), and `currentSince[21]` (Used-Good). Additionally, if `deal_object.current[14]` indicates the Buy Box is 'Used', also consider `currentSince[32]` (buyBoxUsedPrice timestamp). Select the most recent valid timestamp from this combined pool.

**General Timestamp Conversion:**
All Keepa minute timestamps should be converted to datetime objects using `KEEPA_EPOCH = datetime(2011, 1, 1)`, then localized from naive UTC to aware UTC (`timezone('UTC').localize(dt)`), and finally converted to 'America/Toronto' (`astimezone(TORONTO_TZ)`), formatted as '%Y-%m-%d %H:%M:%S'. Timestamps <= 100000 are generally considered invalid/too old.

**The "Keepa Epoch Bug" (Jan 2026):**
A critical regression occurred when the system interpreted Keepa timestamps using an epoch of `2000-01-01` instead of `2011-01-01`. This 11-year offset caused fresh 2026 data to be seen as 2015 data ("Ancient Data"), causing the ingestion pipeline to reject everything. **Always verify the epoch is 2011.**

### Circular Dependencies & Module Structure
-   **`keepa_deals/new_analytics.py`**: This module was specifically created to house downstream analytical logic (e.g., trend calculations, offer count averages) to prevent circular imports between `processing.py`, `stable_calculations.py`, and `stable_products.py`.
-   **Rule:** If you are adding a new metric that depends on core calculations (like inferred sales) but is used by the main processing loop, place it in `new_analytics.py` rather than modifying the core stable modules.

### Data Standards & Epochs
- **Keepa Epoch:** The system strictly uses `datetime(2011, 1, 1)` as the epoch for interpreting Keepa API timestamps. This differs from the 2000 epoch used in some other contexts or documentation. Failure to use 2011 results in an 11-year data offset.

### Token Management & Rate Limiting
- **Blocking Wait Strategy:** To prevent API 429 (Too Many Requests) errors, the system employs a "Blocking Wait" strategy.
- **Implementation:** API wrapper functions (like `fetch_deals_for_deals` in `keepa_deals/keepa_api.py`) accept a `token_manager` argument. If provided, the function calls `token_manager.request_permission_for_call()` which sleeps the thread until sufficient tokens are available, rather than failing immediately.
- **Rule:** When adding new API calls to high-volume loops, always ensure they are integrated with the `TokenManager` to support this flow.
