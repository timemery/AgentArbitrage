# Centralize SQLite Connection Setup and Fix Resource Leaks

**Date:** 2026-05-11
**Status:** Successful

## Task Overview
A latent SQLite lock-contention bug surfaced in production resulting in WSGI requests hanging indefinitely, triggering Gateway Timeouts. The application previously opened SQLite connections via `sqlite3.connect(DB_PATH)` throughout the codebase, failing to set `busy_timeout` or `journal_mode=WAL` consistently on the connections. A temporary monkey-patch was placed in `wsgi.py` as an emergency hot-fix.

The goal of this task was to introduce a centralized database connection helper (`get_db_connection`) in `keepa_deals/db_utils.py` to set the necessary PRAGMAs (`busy_timeout=5000` and `journal_mode=WAL`) uniformly, replace all usages across the codebase, and safely remove the emergency patch from `wsgi.py`. Additionally, a subsequent issue of the WSGI daemon hanging was identified and required fixing.

## Challenges Faced
1. **Recursion Errors:** An initial string-replace script erroneously replaced `sqlite3.connect` within the newly created `get_db_connection` helper itself, leading to a `RecursionError`.
2. **Syntax Errors:** When dynamically inserting the new import (`from keepa_deals.db_utils import get_db_connection`) into scripts, the insertion was accidentally placed inside a multi-line import block in `keepa_deals/Keepa_Deals.py`, causing a `SyntaxError`.
3. **Database Leaks Leading to Hangs:** The most critical challenge was encountered after the initial deployment. Replacing `sqlite3.connect` with `get_db_connection` did not prevent the WSGI daemon from hanging. It was discovered that in several places across the codebase (such as the `api_deals` endpoint in `wsgi_handler.py` and various diagnostic scripts), database connections were being assigned directly (`conn = get_db_connection(...)`) instead of using a `with` context manager. This resulted in unclosed database connections leaking on certain execution paths (like when exceptions occurred and a 500 error was returned without closing the connection). Since SQLite restricts certain PRAGMA statements on concurrent connections when other connections remain unclosed, this led to severe lock contention and Gateway Timeouts.
4. **Test Mocks:** Unit tests patching `sqlite3` directly (like in `test_smart_ingestor_batching.py`) failed because the modules under test were now using the `get_db_connection` helper from `db_utils`.

## Actions Taken
1. **Centralized Helper Setup:**
   Added `get_db_connection(db_path=None, timeout=5.0)` to `keepa_deals/db_utils.py` to wrap `sqlite3.connect` and enforce `busy_timeout=5000` and `journal_mode=WAL`.
2. **Global Replacement:**
   Wrote a robust Python script to scan the codebase, inject the necessary import statement safely, and replace all instances of `sqlite3.connect` with `get_db_connection` while preserving `timeout` kwargs where applicable. Addressed the `SyntaxError` in `Keepa_Deals.py` manually.
3. **Monkey-Patch Removal:**
   Restored `wsgi.py` to its original minimal form, discarding the monkey patch.
4. **Leak Resolution:**
   Audited the codebase for `conn = get_db_connection(...)` assignments operating outside of a `with` context block.
   - For `wsgi_handler.py`, inserted explicit `conn.close()` calls guarded by `if 'conn' in locals() and conn:` inside `except` and `finally` blocks for endpoints like `api_deals`.
   - For standalone scripts (e.g., `Diagnostics/` folder and `recalculator.py`), safely appended a global `conn.close()` wrapped in an exception handler at the end of the script to guarantee cleanup before exiting.
5. **Testing & Verification:**
   - Modified `test_smart_ingestor_batching.py` to correctly patch `keepa_deals.smart_ingestor.get_db_connection` instead of `sqlite3`.
   - Successfully ran the entire test suite via `./run_tests.sh`.

## Conclusion
The task was successful. The codebase now uniformly enforces safe concurrency boundaries for SQLite by routing all connections through the centralized helper. Additionally, hidden resource leaks were closed out across the WSGI daemon and the diagnostic footprint, resolving the Gateway Timeout hangs without re-introducing the monkey-patch.

**Note for future deployments:** The sandbox environment deployment process might differ from Tim's production deployment (`./deploy_update.sh`). This change strictly relies on restarting the WSGI daemon/Celery workers for the new `db_utils.py` helper logic to take effect.
