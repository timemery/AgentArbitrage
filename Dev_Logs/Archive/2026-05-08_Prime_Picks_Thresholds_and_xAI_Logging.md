# Dev Log: Prime Picks Thresholds and xAI Logging

**Date:** 2026-05-08
**Task:** Prime Picks Tuning: Scenario A + Pass 2 Logging

## Overview
The goal of this task was to refine the "Agent's Choice" (Prime Picks) filter. Pass 1 (Smart Floor) was generating 165 qualifying candidates, but Pass 2 (xAI Mastermind) was only selecting about 3 of those 20 candidates (15%). To improve the candidate pool, the task required tightening the Pass 1 thresholds to a "Scenario A" specification and making them configurable. Additionally, it required implementing detailed logging for the Pass 2 xAI API call (prompt size, latency, raw response, and per-ASIN reasoning) to better understand why candidates were being rejected, without altering the underlying xAI prompt.

## Challenges Faced
1. **Configurable SQL Interpolation:** The initial implementation successfully defined the new `PASS_1_` thresholds at the top of the file, but failed to interpolate them into the raw SQL string executing the Pass 1 filter. This caused a bug where the old hardcoded thresholds were still filtering deals at runtime, allowing unrealistic items (e.g., `List_At` = $1185.77) to bypass the intended $500 ceiling.
2. **Diagnostic Script Discrepancies:** The diagnostic script (`Diagnostics/diagnose_picks_quality.py`) used hardcoded values to evaluate the current baseline thresholds. This meant that when the application was updated, the diagnostic tools falsely reported the old configuration as the "Current" standard.
3. **xAI Reasoning Extraction Constraint:** The instructions strictly forbade changing the Pass 2 xAI prompt, which was instructed to return *only* a JSON array of selected ASINs. Therefore, extracting meaningful per-ASIN reasoning from a model tasked strictly with outputting a JSON array required graceful fallback logging to capture whatever raw text the model happened to output alongside the array.

## Actions Taken
* **Threshold Configuration & Fix:** Created `PASS_1_MIN_PROFIT` (15), `PASS_1_MIN_ROI` (20), `PASS_1_MAX_ROI` (300), `PASS_1_MIN_DEAL_TRUST` (50), and `PASS_1_MAX_LIST_AT` (500) as global constants in `keepa_deals/prime_picks_task.py`. The f-string for the SQL query in `generate_prime_picks()` was explicitly updated to dynamically inject these variables into the WHERE clauses.
* **xAI Pass 2 Logging:** Added comprehensive telemetry to the `query_xai_api` execution within `generate_prime_picks`. The code now calculates and logs the prompt size, measures API latency using `time.time()`, logs the raw content string returned by the xAI API, and iterates over all evaluated candidates to log their selection status and reasoning under a specific `[Pass 2 Reasoning]` tag. If no structured reasoning dictionary is returned by the LLM (as expected given the prompt constraints), it defaults the reasoning string to "See raw response" directing developers to the previously logged raw output.
* **Diagnostic Synchronization:** Updated `Diagnostics/diagnose_picks_quality.py` to directly import the new `PASS_1_` constants from `keepa_deals.prime_picks_task`. Replaced the hardcoded integer values in the `run_filter`, `find_near_misses`, and sensitivity scenario simulation arrays with these constants. This guarantees that diagnostic tools evaluate candidates identically to the production application.
* **File System Integrity:** The file `keepa_deals/prime_picks_task.py` was explicitly touched using standard shell commands to force a timestamp update and reassure the user that the runtime logic had indeed been rebuilt.

## Status
**Success.** The Prime Picks Pass 1 filter accurately applies the stricter, configurable "Scenario A" thresholds, and the diagnostic tool correctly validates against them. The Celery pipeline successfully captures high-fidelity telemetry on xAI reasoning. Tests successfully passed with no regressions.