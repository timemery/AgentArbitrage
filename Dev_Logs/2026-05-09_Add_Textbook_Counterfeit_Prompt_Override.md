# Dev Log: Add Textbook Counterfeit Prompt Override

**Date:** 2026-05-09
**Task Overview:**
The goal of this task was to address an issue where the xAI integration in the Prime Picks pipeline (Pass 2 Mastermind) was overcautiously rejecting textbook deals due to perceived counterfeit risk based purely on their category. The user confirmed this behavior was too strict and provided a specific four-factor test that must be met to genuinely identify a counterfeit risk. The task involved adding this explicit override into the Mastermind prompt to take precedence over any conflicting strategies.
Additionally, there was an initial request to fix a Mentor Chat regression that was failing with an "Error communicating with mentor" message.

**Challenges Faced:**
1. **Locating the correct prompt:** The Prime Picks prompt is located in `keepa_deals/prime_picks_task.py`. The text needed to be injected after the strategy dump but before the strict JSON formatting requirement to ensure the LLM prioritized it properly without breaking the JSON-only constraint.
2. **Mentor Chat Regression:** During the investigation of the Mentor Chat regression in `wsgi_handler.py`, the exact error was not being logged to the traceback. I added a `logger.exception()` block to catch the `KeyError`/`IndexError` when parsing the AI response to diagnose the problem.
3. **Ghost Regression Resolution:** Before a full fix for the Mentor Chat regression could be identified via the logs, the user reported that the issue was transient and had self-resolved in production. The task was therefore descoped to only the prompt override.
4. **Environment Consistency:** While working with temporary test files to manipulate logs and debug the Mentor Chat issue, several garbage files were created (`fix_log.py`, `deploy_temp.sh`, etc.) which needed to be cleaned up carefully so that only the targeted change in `prime_picks_task.py` remained. Additionally, `xai_token_state.json` was incidentally touched during test runs and needed to be restored from the index.

**Actions Taken:**
- Modified the `prompt` string in `keepa_deals/prime_picks_task.py` to append the explicit textbook counterfeit risk correction immediately before the JSON instruction. The text includes the precise 4-factor criteria (Sales Rank < 100k, low price, New/Like-New condition, limited seller feedback).
- Verified the integrity of the patch using `run_tests.sh` and ensuring no regressions occurred in the core test suite.
- Reverted all temporary files and logging adjustments initially introduced for the Mentor Chat investigation since that issue self-resolved.
- Committed the prompt update cleanly.

**Task Outcome:**
The task was **successful**. The prompt override was successfully implemented. To verify in production, a Prime Picks refresh should be triggered and `Diagnostics/extract_pass2_reasoning.py` should confirm that textbooks are no longer being categorically rejected for counterfeit risk unless they hit the specific 4 criteria. The expected behavior is an increase in the selection ratio for valid textbooks.
