### **Dev Log Entry**

**Dev Log - Task: Fix Persistent Celery Worker Failure (December 4, 2025)**

**Objective:** Resolve an issue where the `backfill_deals` Celery task was either running stale code or failing to run at all, resulting in a stalled process and null data in the database.

**Summary:** The task was **unsuccessful**. Despite a comprehensive investigation that uncovered and fixed several smaller bugs, the primary environmental issue causing the Celery worker to fail silently on startup could not be resolved.

**Investigation and Actions Taken:**

1. **Initial Hypothesis: Stale Code Cache:** The initial diagnosis was that stale `__pycache__` files owned by the `www-data` user were causing the worker to run old code. The `kill_everything.sh` script was modified to use `sudo rm -rf` for more forceful cache clearing. **Result:** This did not resolve the issue.
2. **Hypothesis: Code Logic Bug in `TokenManager`:** The symptoms (stalling before any API call, no token consumption) pointed to an issue in the `token_manager.py` script.
   - A diagnostic script (`diag_token_manager.py`) was created to isolate the `TokenManager`.
   - This successfully identified a critical bug: the `sync_tokens()` method was not returning a value, causing a `TypeError`.
   - The bug was fixed and verified with the diagnostic script.
   - **Result:** The fix was correct, but the Celery task in the user's environment still exhibited the exact same failure, proving the issue was environmental and the worker was not running the newly fixed code.
3. **Hypothesis: Stale Code / Incorrect Working Directory:** The primary focus shifted to why the Celery worker was not loading the new code.
   - The `celery.log` file revealed the worker was advertising a long-deleted task (`importer_task`), confirming it was loading an old version of the application.
   - The `--workdir` flag was added to the Celery startup commands in `start_celery.sh`.
   - A focused diagnostic script (`test_launch.sh`) captured a previously silent error: `Error: No such option: --workdir`. The Celery version in use was too old for this flag.
   - The `--workdir` flag was subsequently removed.
4. **Hypothesis: User Context / Shell Environment Failure:** With the command itself corrected, the investigation focused on why the `su` or `sudo` commands were failing silently.
   - Checked the `www-data` user's shell via `/etc/passwd`; it was correctly set to `/bin/bash`, disproving the "nologin" shell theory.
   - Switched the startup script's user-switching mechanism from `sudo -u www-data` to `su -s /bin/bash ... www-data`.
   - Removed a nested `nohup` command from the startup script, suspecting a "double nohup" was causing the process to detach incorrectly.
   - **Result:** None of these changes resolved the silent startup failure. At every step, the `celery_worker.log` remained static, showing old log entries, proving the new worker process never successfully launched to the point of writing to its log file.

**Conclusion:** The root cause is a deep, persistent environmental issue that prevents the `start_celery.sh` script from successfully launching the Celery worker daemon as the `www-data` user. The failure is completely silent, with no errors being written to any of the monitored logs. The problem is not with the Python application code itself but with the shell execution environment. The task is being handed off for a fresh perspective on this environmental challenge.