# Prime Picks Quality Diagnostic
**Date:** 2026-05-08

## Overview of the Task
The goal was to create a read-only diagnostic script (`Diagnostics/diagnose_picks_quality.py`) to analyze the "Prime Picks" tuning pipeline against the production database. This script provides a detailed report on pick quality, threshold sensitivity, near-misses, top-of-pool candidate clustering, and the pass-2 (xAI) selection ratio. The purpose of this report is to inform future adjustments to the Pass 1 filtering criteria without currently modifying any pipeline logic or thresholds.

## Challenges Faced
1. **Schema Nuances (`Deal_Trust` vs `Profit_Confidence`)**: During script development, attempts to fetch the `Deal_Trust` column directly resulted in `OperationalError`s and `KeyError`s because the database schema in the sandbox environment currently uses `Profit_Confidence` as a fallback or proxy for `Deal_Trust` based on recent schema changes.
2. **Database Connection Configuration**: A `sqlite3.OperationalError: no such table: deals` occurred when the script was initially executed from the `Diagnostics/` folder because it was attempting to create or access a SQLite database in the wrong relative directory.
3. **Datetime Deprecation Warnings**: The standard usage of `datetime.utcnow()` triggered deprecation warnings in Python 3.12, which cluttered the script's stdout output and slightly reduced its intended "clean" paste-ability.

## Solutions Addressed
1. **Adaptive Column Lookup**: Programmed the diagnostic script to check for `Deal_Trust` and gracefully fallback to `Profit_Confidence` if needed, ensuring stability regardless of whether the sandbox or production database contains the exact `Deal_Trust` column yet.
2. **Standardized DB Pathing**: Updated the script to explicitly import `DB_PATH` from the centralized `keepa_deals.db_utils` module, guaranteeing that it consistently points to the correct `deals.db` located at the root directory, regardless of where the script is executed.
3. **Timezone-Aware Datetimes**: Refactored the `get_hours_since` timezone conversion logic to strictly use `datetime.now(timezone.utc)` and ensure all datetime objects are timezone-aware, effectively resolving the deprecation warnings and producing a much cleaner standard output.

## Conclusion
The task was highly successful. The diagnostic script now properly accesses the production database in a strictly read-only fashion, calculates all relevant ROI and Score logic mathematically matching the Pass 1 pipeline, simulates different configuration sensitivity thresholds, and generates a formatted, clean plain-text report ready for manual review. No production paths, AI prompts, or configuration thresholds were modified, maintaining strict adherence to all stated AGENTS.md rules.
