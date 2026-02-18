# Dev Log: Diagnostics and Test Suite Standardization

**Date:** 2026-02-04
**Author:** Jules (AI Agent)
**Status:** Successful

## Task Overview
The goal of this task was to "cull" the overwhelming number of diagnostic and test scripts that had accumulated in the repository. The user requested a standardized, manageable suite of tools to run before and after tasks, specifically highlighting `system_health_report.py`, `comprehensive_diag.py`, and `diagnose_dwindling_deals.py` as the core useful scripts.

## Challenges Faced

1.  **Script Overload:** The `Diagnostics/` folder contained over 50 scripts, many of which were redundant (e.g., `check_binding_coverage.py`, `debug_deal_rejection.py`) or obsolete (e.g., `fix_stalled_system.py`, which predated the current Redis lock architecture).
2.  **Test Dependencies (Pytest vs Unittest):** While standardizing the test suite, I discovered that two tests (`tests/test_janitor.py` and `tests/test_auth_phase1.py`) relied on `pytest`, which was not installed in the standard environment (causing `ImportError`). The rest of the suite used the standard library's `unittest`.
3.  **Environment Stability:** The initial diagnostic run failed completely because the sandbox environment lacked the necessary `.env` file and Redis service, which is expected behavior for a fresh sandbox but required careful interpretation to verify the *scripts* were working, even if the *environment* was empty.

## Actions Taken

### 1. The "Great Cull" (Archiving)
Instead of deleting potentially useful code, I created `Legacy/` subdirectories in both `Diagnostics/` and `tests/`.
*   **Diagnostics:** Moved 42 obsolete scripts to `Diagnostics/Legacy/`.
*   **Tests:** Moved 2 non-core scripts (`verify_fix_test.py`, `test_diagnose_script.py`) to `tests/Legacy/`.

### 2. Standardization of the Core Suite
I created a master script `Diagnostics/run_suite.sh` that executes the three critical diagnostics in the correct order:
1.  **System Health (`system_health_report.py`):** Checks infrastructure (Redis, Celery, API Keys).
2.  **Deal Stats (`comprehensive_diag.py`):** Checks database integrity vs API counts.
3.  **Pipeline Flow (`diagnose_dwindling_deals.py`):** Checks for zombie locks and stale data.
4.  **Log Tail:** Tails `celery_worker.log` for immediate error visibility.

### 3. Test Suite Unification
To ensure `run_tests.sh` could run reliably without external dependencies:
*   Refactored `tests/test_janitor.py` from `pytest` to `unittest`.
*   Refactored `tests/test_auth_phase1.py` from `pytest` to `unittest`.
*   Created `run_tests.sh` to discover and run all `test_*.py` files in `tests/`, explicitly ignoring the `Legacy/` folder.

### 4. Documentation
Created `Diagnostics/README.md` to serve as the source of truth for which scripts are part of the active suite and what each one does.

## Outcome
The task was **successful**. The `Diagnostics/` directory is now clean, containing only the 7 core scripts + the README and the `Legacy/` folder. The `run_suite.sh` script provides a single entry point for health checks, and `run_tests.sh` ensures regression testing is a one-line command.
