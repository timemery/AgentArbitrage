# Dev Log: Fix "Advice from Ava" API Connectivity & Crash

**Date:** January 1, 2026
**Task:** Debug and Fix "Advice from Ava" (The "Coffee Break" Error)
**Status:** Success

## 1. Overview

The "Advice from Ava" feature, which uses the xAI API to generate arbitrage advice for books, was failing in the production environment (WSGI) while working correctly in standalone CLI scripts. The error manifested as a generic "Ava is taking a coffee break" message or a red error string. The objective was to diagnose the discrepancy between the environments and ensure the feature works reliably in the dashboard.

## 2. Diagnostics & Challenges

### Challenge 1: Lack of Visibility

Initial logs were insufficient to pinpoint the error. The application was catching exceptions genericallly or failing silently in the background thread, masking the true root cause.

- **Action:** I instrumented `keepa_deals/ava_advisor.py` with verbose logging, including masking the API key to verify its presence, logging the exact HTTP status codes from xAI, and most importantly, printing full Python tracebacks for any exceptions.

### Challenge 2: The "Environment Gap" Hypothesis

We initially hypothesized that `os.getenv('XAI_TOKEN')` was failing in the WSGI context due to how `load_dotenv()` works with relative paths.

- **Action:** To rule this out, I refactored `ava_advisor.py` to accept an optional `api_key` argument (Dependency Injection pattern) and updated `wsgi_handler.py` to explicitly pass the loaded key. This ensured the key was available regardless of the module's internal environment state.

### Challenge 3: The Real Root Cause (Data Type Mismatch)

Once logging was active, the traceback revealed the actual culprit was **not** the API connection, but a `ValueError` in the data preparation phase:

```
ValueError: Unknown format code 'f' for object of type 'str'
```

This occurred in the `format_currency` helper function. The database or the deal object was returning price fields (like `1yr_Avg` or `Best_Price`) as **strings** (e.g., `"$25.00"` or `"25.00"`) instead of floats. The code attempted to format them using an f-string with `:,.2f`, which is only valid for numeric types, causing the thread to crash before the API call could be attempted.

## 3. Implementation Details

### Fix 1: Robust Currency Formatting

I modified `format_currency` in `keepa_deals/ava_advisor.py` to be defensive:

```
def format_currency(value):
    if value is None:
        return "-"
    try:
        # Attempt to clean and convert string inputs
        if isinstance(value, str):
            value = float(value.replace('$', '').replace(',', ''))
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        # Fallback: return original value if conversion fails
        return str(value)
```

### Fix 2: Explicit Error Handling

I wrapped the main logic in `generate_ava_advice` with a broad `try/except` block. This ensures that even if a data error occurs, it is logged with a traceback, and a user-friendly error message is returned instead of crashing the worker process.

### Fix 3: Explicit API Key Passing

I updated the call site in `wsgi_handler.py` to pass the `XAI_API_KEY` explicitly:

```
advice = generate_ava_advice(deal_data, xai_api_key=XAI_API_KEY)
```

## 4. Verification

- **Reproduction Script:** Created `reproduce_issue.py` which mimicked the WSGI environment and fed string data into the function. It successfully reproduced the crash before the fix and confirmed the fix afterwards.
- **Production Log Analysis:** Confirmed via `app.log` that the `ValueError` stopped occurring and the "Advice" text was successfully generated.

## 5. Key Learnings & References

- **Trust No Data Type:** SQLite data types can be loose. Always sanitize or cast numeric fields (Prices, Ranks, Counts) before applying strict string formatting operations.
- **Fail Gracefully:** External service wrappers (like AI advisors) must catch *all* exceptions to prevent crashing the main application thread.
- **WSGI vs CLI:** Environment variables behave differently. Explicitly passing configuration values (Dependency Injection) is safer than relying on `os.getenv` inside deep modules.

# Dev Log: Refine Strategy Data for AI Consumption

**Date:** February 6, 2025 **Task ID:** Refine Strategy Data **Status:** Success

## 1. Task Overview

The objective was to transition the "Strategy Database" (`strategies.json`) from a simple list of unstructured text strings (e.g., "Buy books with rank < 50k") into a structured JSON format. This transformation allows the "Advice from Ava" feature to programmatically parse, filter, and apply specific strategies based on deal context (e.g., filtering out "Seasonality" advice for non-seasonal items) rather than feeding generic text blobs to the AI.

## 2. Key Objectives & Requirements

- **Structured Schema:** Define a JSON schema including `id`, `category`, `trigger`, `advice`, and `confidence`.
- **Migration Utility:** Create a script to convert existing legacy text data into the new schema using an LLM.
- **Context-Aware Advice:** Update `ava_advisor.py` to filter strategies dynamically based on the deal being analyzed.
- **Backward Compatibility:** Ensure the system handles a "hybrid" state (containing both legacy strings and new JSON objects) without crashing during the transition period.

## 3. Challenges & Resolutions

### A. Hybrid Data Compatibility

- **Challenge:** The `strategies.json` file is the production database. Instantaneously converting it could break the live application if the code wasn't ready, and deploying code before data migration would cause crashes if the app expected objects but found strings.

- Resolution:

   

  implemented "Defensive Parsing" in

   

  ```
  wsgi_handler.py
  ```

  . When loading strategies, the system checks the data type of each entry.

  - If it is a `dict` (structured), it is used as-is.
  - If it is a `str` (legacy), it is wrapped on-the-fly into a temporary object (`{'advice': <string>, 'category': 'Legacy'}`), preventing runtime errors (`AttributeError: 'str' object has no attribute 'get'`).

### B. Frontend Rendering of Mixed Types

- **Challenge:** The `strategies.html` Jinja2 template initially failed when iterating over the list because it tried to access keys like `strategy.category` on string objects, causing a 500 Internal Server Error.

- Resolution:

   

  Updated the template logic to explicitly check type:

   

  ```
  {% if strategy is mapping %}
  ```

  .

  - **Mapping (Dict):** Renders a structured 5-column table row.
  - **String:** Renders a fallback row with "Legacy" as the category and the string content in the advice column.
  - Verified this visually using a Playwright script (`verify_strategies.py`) which captured screenshots of the UI rendering mixed data correctly.

### C. Migration Reliability

- **Challenge:** Converting 50+ strategies via LLM can be flaky (timeouts, malformed JSON).

- Resolution:

   

  Created a dedicated utility

   

  ```
  migrate_strategies.py
  ```

   

  that:

  - Uses `httpx` for robust API calls.
  - Includes a retry mechanism.
  - Writes to a *new* file `strategies_structured.json` instead of overwriting the source `strategies.json`, allowing for manual verification before the user "swaps" the database.

## 4. Technical Implementation Details

### Schema Definition

We adopted the following schema for actionable strategies:

```
{
  "id": "uuid-v4-string",
  "category": "Risk | Profitability | Seasonality | General",
  "trigger": "Logic condition (e.g., 'rank > 50000')",
  "advice": "Actionable text for the AI persona",
  "confidence": "High | Medium | Low"
}
```

### Module Updates

- **`migrate_strategies.py`**: A CLI tool that reads raw text, sends it to `grok-4-fast-reasoning` with a system prompt enforcing the schema, and saves the structured output.

- `keepa_deals/ava_advisor.py`

  :

  - Added `load_strategies(deal_context)`.
  - **Filtering Logic:** Always includes "General" and "Risk" strategies. Conditionally includes "Seasonality" only if the deal's title or extracted fields imply seasonality.

- `wsgi_handler.py`

  :

  - Updated the `/approve` route to parse incoming JSON payloads from the "Guided Learning" module.
  - Added a deduplication check based on the `advice` text content to prevent duplicate entries when re-running migrations.

## 5. Outcome

The task was successfully completed. The system now supports a highly granular advice engine.

- **Before:** The AI received a dump of all 50+ text tips for every single deal, diluting the context.
- **After:** The AI receives a targeted subset of rules relevant to the specific book (e.g., only High Rank rules for high-rank books), resulting in higher quality, specific advice.
- **Safety:** The application is fully backward compatible and safe to deploy even before the data migration script is run.

------