# Dev Log: Fix WSGI Hangs in Production
**Date:** 2026-05-12
**Task Overview:**
The primary objective of this task was to diagnose and resolve a critical regression where all WSGI requests to the application were hanging in production, eventually returning a 504 Gateway Timeout after 60+ seconds.

**Challenges Faced:**
The issue was notoriously difficult to diagnose because:
1. The application code (Flask routes, database layer, imports) worked flawlessly when run directly via the CLI in the production environment.
2. The `keepa_deals.db_utils.get_db_connection` helper itself was sound when called in isolation.
3. The hang produced *no* Python traceback or exception in the Apache logs (save for a generic NumPy sub-interpreter `UserWarning`).
4. We had to create a standalone Python diagnostic script (`Diagnostics/diagnose_wsgi_hang.py`) that could simulate WSGI requests, enforce timeouts, and attempt to dump thread stack traces and connection leak counts without modifying the Apache environment or production source code.

**What Was Done:**
1. **Diagnostic Script Creation:** A `diagnose_wsgi_hang.py` script was written. It used the Flask test client and Python's `threading` and `sys._current_frames()` to simulate routing and trace thread execution.
2. **Analysis:** When run on the production server, the diagnostic script executed all routes (including `/`, `/dashboard`, `/api/deals`) in milliseconds with a 100% success rate and zero connection leaks.
3. **Root Cause Identification:** The fact that the code worked perfectly in the native Python interpreter but hung completely without a stack trace under `mod_wsgi` strongly pointed to a C-extension deadlock. Specifically, `mod_wsgi` spawns sub-interpreters for application isolation. Certain Python C-extensions (like `sqlite3`, which was heavily utilized by the newly deployed `get_db_connection` helper, and `numpy`) maintain global C-state that is fundamentally incompatible with sub-interpreters.
4. **Resolution:** We modified the Apache virtual host configuration file (`agentarbitrage.conf`) and added the `WSGIApplicationGroup %{GLOBAL}` directive to the `<VirtualHost *:443>` block. This configuration change forces `mod_wsgi` to run the application within the main Python interpreter instead of an isolated sub-interpreter, effectively sidestepping the C-extension incompatibility.

**Task Status:**
**Successful.** Following the application of the `WSGIApplicationGroup %{GLOBAL}` directive and a subsequent restart of the Apache service, the site was restored and the hanging WSGI request issue was completely resolved.