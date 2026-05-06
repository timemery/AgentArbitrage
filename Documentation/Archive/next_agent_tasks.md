# Next Agent Tasks: Resolve Pass 2 Prime Picks Filter

The previous agent attempted to update the model used in the "Agent's Choice" Pass 2 filtering pipeline (`wsgi_handler.py`). The original model (`grok-beta`) was failing with `429` timeouts.

The previous agent updated it to `grok-4-fast-reasoning`. This was tested with a new diagnostic script (`Diagnostics/verify_agents_choice_model.py`) and it successfully returns correctly formatted JSON arrays of ASINs.

However, the previous agent struggled heavily with Git and the code review tool, polluting the repository with scratchpad files and accidentally overwriting `parse_log.py` at one point. The session was aborted due to time constraints before a clean submission could be made.

### Your Objectives:
1. **Verify `wsgi_handler.py`:** Ensure that the `model` in the `query_xai_api` payload for Pass 2 (around line 1768) is set to a valid, robust model (e.g., `grok-4-fast-reasoning`).
2. **Review Diagnostic Script:** Verify that `Diagnostics/verify_agents_choice_model.py` exists and correctly runs to test the model.
3. **Clean the Repository:** Ensure absolutely no scratchpad files (like `test_pass1.py` or temporary json logs) exist in the git index or working directory.
4. **Submit cleanly:** Run the test suite (`./run_tests.sh`) and execute the pre-commit instructions, ensuring that the only changes you are committing are the specific `wsgi_handler.py` fix, the diagnostic script, and the dev log.
