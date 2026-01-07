# Dev Log: Feature Implementation - Advice from Ava (Attempt 1)

**Date:** January 2026 **Task:** Implement "Advice from Ava," an AI-powered feature displaying actionable, deal-specific advice in the dashboard overlay.

### 1. Objective

Create a feature that replaces Keepa chart analysis with a concise, AI-generated paragraph.

- **Input:** Deal metrics (Price, Sales Rank, Seasonality, Profit, Trends) and learned strategies from `strategies.json`.
- **Output:** A 50-80 word actionable advice paragraph displayed in the deal overlay.
- **Technology:** xAI API (Grok).

### 2. Implementation Details

**A. Backend Module (`keepa_deals/ava_advisor.py`)**

- Created a standalone module to handle the advice generation logic.
- **Prompt Engineering:** Constructs a "Persona" for Ava (wise, cautious, encouraging) and formats deal data into a structured prompt.
- **Strategy Injection:** Attempts to load `strategies.json` and injects its content into the system prompt to inform the AI's reasoning.
- **API Client:** Uses `httpx` to communicate with the xAI API. Implemented lazy loading of the `XAI_TOKEN` to prevent import-time errors.

**B. API Endpoint (`wsgi_handler.py`)**

- Added route `/api/ava-advice/<string:asin>`.
- Fetches the deal row from the `deals` database table.
- Passes the deal dictionary to `ava_advisor.generate_ava_advice`.
- Returns JSON: `{'advice': "..."}` or `{'error': "..."}`.

**C. Frontend (`templates/dashboard.html`)**

- Added a container div `#ava-advice-container` within the "Profit" tab of the deal overlay.

- Implemented



  ```
  loadAvaAdvice(asin)
  ```



  function:

  - Triggered on row click.
  - Displays a "Analyzing deal data..." state with a spinner.
  - Updates the text content with the API response.
  - **Error Handling Update:** Modified to display specific error messages (e.g., "Error: 404 Not Found") in red, rather than a generic fallback, to aid debugging.

### 3. Challenges & Technical Hurdles

**A. xAI Model Versions**

- **Issue:** Initial implementation used `grok-4-latest`, based on an assumption of the naming convention. This resulted in `404 Not Found` API errors.
- **Confusion:** The error message suggested using `grok-3` (implying it was the latest), but this was a generic deprecation notice for `grok-beta`.
- **Resolution:** Identified that the correct, high-performance model used elsewhere in the codebase (e.g., `seasonality_classifier.py`) is `grok-4-fast-reasoning`. The code was updated to use this model.

**B. Environment Variable Loading**

- **Issue:** `ava_advisor.py` initially tried to access `os.getenv("XAI_TOKEN")` at the top level (module scope). Because `wsgi_handler.py` imports this module *before* calling `load_dotenv()`, the token was `None`, causing immediate failures.
- **Resolution:** Refactored `ava_advisor.py` to fetch the token lazily *inside* the `query_xai_api` function, ensuring the environment is fully loaded before access.

**C. Frontend Error Masking**

- **Issue:** The initial JavaScript implementation caught all errors and displayed a generic "Ava is taking a coffee break" message. This hid the critical `404` and `401` errors occurring on the backend.
- **Resolution:** Updated the frontend to render the specific `error` message returned by the JSON API if present.

### 4. Current Status & Known Issues

- **Status:** The code is deployed. Backend unit tests (running isolated scripts with mock data) succeed and generate high-quality advice using `grok-4-fast-reasoning`.
- **Production Issue:** The integrated feature in the live web application continues to return the fallback/error state ("Ava is taking a coffee break"). This implies the API call from the web server is failing, timing out, or encountering an unhandled exception despite the isolated tests passing.

### 5. Reference for Next Agent

- **Files Modified:** `keepa_deals/ava_advisor.py`, `wsgi_handler.py`, `templates/dashboard.html`.
- **Investigation Point:** The discrepancy between the working diagnostic script (`verify_ava_backend.py`) and the failing web app suggests an environment difference in the WSGI context. Check if the web server process has outbound internet access to `api.x.ai` or if the `XAI_TOKEN` is correctly propagating to the Flask child process.
- **Strategy Data:** The integration reads `strategies.json`, but a mechanism to *create/update* this file from the Strategy Database (as mentioned in the task description) is not part of this implementation and needs to be addressed in a separate task.
