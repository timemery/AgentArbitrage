# Next Task: Finalize Advice Speed & Homogenization

**Priority:** High
**Context:**
The previous agent implemented a caching mechanism for `strategies.json` and `intelligence.json` to solve slow loading times (10-12s). They also built an asynchronous "Homogenization" feature (semantic deduplication using xAI) to clean up the `intelligence.json` database. This was moved to a background Celery task to prevent HTTP timeouts.

**Current State:**
- **Backend:** `wsgi_handler.py` has been updated to dispatch `homogenize_intelligence_task` asynchronously and expose a `/api/homogenize/status` endpoint.
- **Worker:** `keepa_deals/maintenance_tasks.py` contains the Celery task logic using chunking (batch 500) to process the list via LLM.
- **Frontend:** `intelligence.html` has new buttons for "Remove Duplicates" (Exact) and "Homogenize" (Semantic) with polling logic.
- **Data:** `intelligence.json` was *not* updated in the last commit to preserve data integrity for your verification.

**Immediate To-Dos for Next Agent:**

1.  **Verify Production Deployment:**
    *   Ensure the new Celery task `keepa_deals.maintenance_tasks.homogenize_intelligence_task` is registered by the worker. You may need to check `celery_worker.log` after a restart.
    *   The previous agent's deployment script (`deploy_update.sh`) includes a `touch wsgi.py` and service restart, which should be sufficient, but verify.

2.  **Test Homogenization Logic:**
    *   Run the verification script `verify_semantic_merge.py` (added in the previous branch) in the production environment.
    *   Monitor `celery_worker.log` to see if the task picks up, processes chunks, and successfully writes to `intelligence.json`.
    *   *Warning:* This process consumes xAI tokens.

3.  **UI Verification:**
    *   Log in as an admin (`tester` / `OnceUponaBurgerTree-12monkeys`).
    *   Go to `/intelligence`.
    *   Click "Homogenize (Semantic)".
    *   Verify the button enters a "Processing..." state and polls successfully until completion.

4.  **Performance Check:**
    *   Load the "Ava Advice" on a deal.
    *   Verify if the response time is now acceptable (< 5 seconds) thanks to the in-memory caching in `keepa_deals/ava_advisor.py`.

5.  **Final Polish:**
    *   If all works, you may want to run the Homogenization once fully to clean the production database, then commit the cleaner `intelligence.json`.
