# Prime Picks Funnel Diagnostic and Cache Preservation

**Date:** 2026-05-08
**Task Overview:**
The primary objective of this task was to create a standalone, read-only Python diagnostic script (`Diagnostics/diagnose_prime_picks.py`) to run against the production SQLite database. The script was designed to identify where the "Prime Picks" deal funnel was collapsing to zero by analyzing each stage of the filtering pipeline. Furthermore, upon identifying intermittent xAI failures as the root cause, the task was updated to ensure that the Prime Picks background task gracefully handles such failures without clearing the cache of previously approved deals.

**Challenges Faced:**
1. **ModuleNotFoundError during Script Execution:** The standalone script failed to import modules from `keepa_deals` because it was not run from the project root and the directory was not in the `PYTHONPATH`.
2. **Identifying the Source of Funnel Collapse:** Initial analysis suggested a potential issue with the timeout configured for the xAI API. The user suspected a strict 10s timeout, but upon code inspection, it was discovered that the `requests.post` call in `ava_advisor.py` was already utilizing a `150.0` second timeout with a `max_retries = 5` loop.
3. **Flawed Fallback Logic in Pass 2:** When the `query_xai_api` eventually failed or returned an empty payload due to intermittent API issues, the fallback logic in `prime_picks_task.py` was wiping the previously cached `prime_picks` from the database and overriding it with unfiltered top candidates from Pass 1, defeating the purpose of the Pass 2 evaluation.

**Actions Taken to Address Challenges:**
1. **Diagnostic Script Implementation:** Wrote a comprehensive script that dynamically extracts the active Pass 1 filtering thresholds from `keepa_deals/prime_picks_task.py` and runs the database rows against them to provide a detailed funnel breakdown (Stages 0-5), including samples of rejected deals and distribution statistics.
2. **Path Resolution Fix:** Modified `diagnose_prime_picks.py` to insert the project root into `sys.path` dynamically before attempting to import `keepa_deals.db_utils`, ensuring seamless execution from any working directory.
3. **Cache Preservation on Failure:** Refactored the fallback logic in `keepa_deals/prime_picks_task.py` for the Pass 2 pipeline. Instead of falling back to unfiltered candidates and inserting them into the database, the task now simply logs the failure and early-exits (`return`). This correctly preserves the most recent valid run of "Prime Picks" in the cache.

**Outcome:**
**Success.** The diagnostic script accurately revealed the pipeline state without causing side effects. The cache preservation update prevents intermittent xAI failures from temporarily emptying or degrading the quality of the Prime Picks displayed on the user's dashboard.
