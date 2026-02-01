# Task: Diagnose and Fix Persistent Service Startup Failure

## Context
The application uses Celery (Worker + Beat) backed by Redis for background processing. Despite implementing a resilient startup script (`start_celery.sh`) with an infinite monitoring loop and robust process detection (`pgrep`), the system diagnostics report consistent failures:
- **Celery Worker**: FAIL - Not Found
- **Celery Beat**: FAIL - Not Found
- **Monitor Process**: PASS - Running

## Current Status
- `start_celery.sh` is running (Monitor Process found).
- The logs show `celery@srv... ready` and `beat: Starting...`, indicating successful *initial* startup.
- However, the services disappear shortly after, or are not detectable by `system_health_report.py`.
- `fix_and_restart.py` was created to automate the reset but the result remains the same.

## Failure Analysis
- **Restart Loop**: The monitor log shows repeated entries of "Services started. Entering monitoring loop..." followed by checks. This suggests `pgrep` inside the loop might still be failing to see the processes, or the processes are crashing silently and being restarted.
- **Process Detection**: We relaxed the regex to `celery.*worker`, but it's possible there is still a mismatch in the environment (e.g. `python` vs `python3` or path issues).
- **Environment**: The logs show `CPendingDeprecationWarning`, which is benign but noisy.

## Goal for Next Agent
Investigate why the Celery Worker and Beat processes are not persisting or are not detectable by the diagnostic script, despite the startup script claiming success.

## Recommended Investigation Areas
1.  **Process Life**: Are the processes crashing immediately? Check `celery_worker.log` for exit codes or tracebacks (beyond the startup logs).
2.  **Detection Logic**: Verify `pgrep -f "celery.*worker"` manually in the shell to see exactly what the process string looks like.
3.  **Concurrency**: Ensure the `while true` loop in `start_celery.sh` isn't spawning multiple conflicting instances.
4.  **Permissions**: Verify if `su -s /bin/bash ... www-data` is actually working as expected in the specific server environment.

## Resources
- `Diagnostics/system_health_report.py` (The main diagnostic tool)
- `Diagnostics/fix_and_restart.py` (Automation wrapper)
- `start_celery.sh` (The startup logic)
- `celery_worker.log` & `celery_monitor.log`
