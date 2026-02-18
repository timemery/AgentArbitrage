# Fix Homogenization Stall

**Date:** 2026-02-03
**Task:** Investigate and fix the stall in the Intelligence Homogenization feature.

## Overview
The "Homogenization" feature, designed to semantically merge duplicate concepts in `intelligence.json` using xAI (`grok-4-fast-reasoning`), was reported to stall indefinitely. The process would be triggered via the API but would not complete, leading to a degraded user experience and potential data inconsistencies.

## Investigation & Challenges

1.  **Silent Stalling:** The primary symptom was that the background task, despite being triggered, did not seem to execute or complete its work.
2.  **Configuration Audit:** An inspection of the Celery configuration revealed the root cause. The Celery worker uses an explicit `imports` list in `celery_config.py` to know which modules contain task definitions.
3.  **Missing Registration:** The module `keepa_deals.maintenance_tasks`, which contains the `homogenize_intelligence_task`, was **missing** from this `imports` list. As a result, the worker was unaware of the task's existence or code, leading to the failure.
4.  **Verification Hurdles:** verifying the fix required running the actual logic. The sandbox environment lacked the necessary `.env` variables (specifically `XAI_TOKEN`) to run the standalone verification script `verify_semantic_merge.py` initially.

## Technical Solution

1.  **Module Registration:** 
    -   Modified `celery_config.py` to add `'keepa_deals.maintenance_tasks'` to the `imports` tuple.
    -   This change forces the Celery worker to import the module on startup, thereby registering the `@celery.task` decorated function.

2.  **Logic Verification:**
    -   Populated the `.env` file with the required `XAI_TOKEN`.
    -   Executed `verify_semantic_merge.py`.
    -   **Result:** The script successfully loaded `intelligence.json`, authenticated with xAI, processed the data in chunks, and correctly identified duplicate concepts (reducing the count from 1232 to 1149 in the test run). This confirmed the underlying logic is sound and functionally correct.

## Outcome
**Successful.**
The module is now correctly registered in the system configuration. The Celery worker will now be able to discover and execute the `homogenize_intelligence_task`. Verification confirmed that the semantic merging logic itself performs as expected.

## Files Changed
-   `celery_config.py`
