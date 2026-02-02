# Task: Purchase Analysis & Advice Speed Optimization & Deduplication

**Date:** 2026-02-02
**Status:** Incomplete / Partially Implemented (Due to Agent Capacity Limits)

## Overview
The primary goal was to address the slow loading times (10-12 seconds) of the "Purchase Analysis & Advice" feature. The user suspected that duplicate entries in the `strategies.json` and `intelligence.json` databases were contributing to the latency. The task involved creating tools to remove duplicates (both exact and semantic) and implementing caching mechanisms to improve performance.

## Challenges Faced
1.  **Large Data Sets & Latency:** The `strategies.json` and `intelligence.json` files had grown significantly, causing file I/O overhead on every request.
2.  **Synchronous Processing Timeouts:** The initial implementation of the "Homogenize" (semantic deduplication) feature ran synchronously within the Flask web request. Because this process involves calling an LLM (xAI) for hundreds/thousands of items, it exceeded the web server's timeout limit, resulting in HTTP 500/504 errors and a frontend `SyntaxError: Unexpected token '<'` (parsing HTML error page as JSON).
3.  **Semantic vs. Exact Duplication:** Simple string matching was insufficient for the "Intelligence" database, which contained conceptually similar but identically phrased ideas.
4.  **Agent Capacity:** The complexity of debugging the async task dispatch, frontend error handling, and environment constraints (production script paths vs. sandbox paths) consumed significant agent context/capacity, leading to a decision to pause the task.

## Actions Taken
1.  **In-Memory Caching:** Implemented logic in `keepa_deals/ava_advisor.py` to cache the contents of `strategies.json` and `intelligence.json` in memory, reloading only when the file modification timestamp (`os.path.getmtime`) changes.
2.  **Exact Deduplication:** Added API endpoints (`/api/remove-duplicates/*`) and UI buttons to scan and remove exact string matches from both databases.
3.  **Async Semantic Homogenization:**
    *   Moved the heavy lifting of semantic merging from `wsgi_handler.py` to a background Celery task (`keepa_deals/maintenance_tasks.py`).
    *   Implemented a chunking strategy (batch size 500) to process the list without hitting LLM context limits.
    *   Added a Redis-based status tracking system (`homogenization_status`) so the frontend can poll for progress.
4.  **UI Updates:** Updated `intelligence.html` to include "Remove Duplicates" and "Homogenize" buttons with polling logic.

## Outcome & Next Steps
While the core infrastructure for optimization (caching) and deduplication (async task) has been implemented and verified via unit tests (`tests/test_homogenization.py`, `tests/test_deduplication.py`), the task is considered incomplete due to agent capacity limits.

**Remaining Issues/To-Do:**
*   Full end-to-end verification of the async task in the production environment (ensuring the Celery worker picks up the new task definition).
*   Potential further optimization of the Advice generation prompt itself, as reducing database size is only one factor in the 10-12s latency.
*   The `intelligence.json` file updates were excluded from the final commit to preserve data integrity for the next session.

**Note:** This task will be continued in a fresh environment to ensure stability and complete the performance tuning.
