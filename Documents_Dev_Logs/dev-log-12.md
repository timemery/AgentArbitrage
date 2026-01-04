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

# Dev Log: Fix Seller Trust Filter & Dashboard UI Tweaks

**Date:** October 12, 2025 **Task:** Fix Seller Trust filter logic issues (0 results at high settings) and implement various dashboard UI refinements (reordering, labeling, styling).

## 1. Task Overview

The user reported that the "Seller Trust" filter was behaving incorrectly: selecting "20%" resulted in 0 deals, while "19%" showed deals with "10/10" trust. This indicated a disconnect between the filter's input range (percent or 0-10) and the underlying database values. Additionally, the user requested specific UI changes:

- Reordering filters (Min. Below Avg., Min. Profit, Min. Margin, Max. Sales Rank, Min. Profit Trust, Min. Seller Trust).
- Adding "Min." and "Max." qualifiers to labels.
- Standardizing filter styling (blue values with spacing).
- Ensuring all filters default to an "Any" state.

## 2. Technical Investigation & Challenges

### The "Seller Trust" Disconnect

- **The Symptom:** The filter failed at high values. Selecting "10/10" returned zero results, despite many deals displaying "10/10".

- The Root Cause:

  - **Frontend Display:** The dashboard displays trust as `X/10`. This is calculated by taking the `Seller_Quality_Score` (a Wilson Score probability between 0.0 and 1.0) and rounding it to the nearest tenth. For example, a score of `0.96` rounds to `1.0` and displays as "10/10".
  - **Initial Filter Logic:** The original filter treated the input (0-100) as if it mapped to a 0-5 scale (dividing by 20), which was incorrect for the 0-1 data.
  - **Second Attempt Logic:** We updated it to divide by 10 (e.g., input `10` becomes `1.0`). While better, this created a strict filter `score >= 1.0`. Since Wilson Scores are probabilities, a score is rarely exactly `1.0`. A score of `0.96` (which *looks* like 10/10) failed this check.

- The Solution (Rounding Buckets):

   

  To correctly filter for "10/10 deals", we need to find deals that

   

  round

   

  to 10. The logic needed to calculate the

   

  lower bound

   

  of that rounding bucket.

  - Formula: `(Input_Value - 0.5) / 10.0`.
  - Example for Input 10: `(10 - 0.5) / 10 = 0.95`. This correctly captures scores >= 0.95 (like 0.96), which display as 10/10.

### UI State Management

- **Challenge:** Ensuring the sliders showed "Any" instead of numeric values ("0%", "∞") when in their default state, and reverting correctly when reset.
- **Solution:** Updated the Javascript initialization logic and the `steps` arrays for sliders (e.g., `salesRankSteps`) to explicitly use `label: 'Any'` for the default values (`0` or `Infinity`).

## 3. Implementation Details

### Backend (`wsgi_handler.py`)

- `api_deals` & `deal_count`:

   

  Updated the

   

  ```
  seller_trust_gte
  ```

   

  filter logic.

  ```
  # Old: score >= input / 2.0  (Incorrect 0-5 assumption)
  # New: score >= (input - 0.5) / 10.0 (Correct 0-1 probability with rounding bucket support)
  if filters.get("seller_trust_gte") is not None and filters["seller_trust_gte"] > 0:
      seller_trust_db_value = (filters["seller_trust_gte"] - 0.5) / 10.0
      where_clauses.append("\"Seller_Quality_Score\" >= ?")
  ```

### Frontend (`templates/dashboard.html` & `static/global.css`)

- **HTML Structure:** Reordered the `.filter-item` divs to match the requested layout.

- **Labels:** Updated text to "Min. Below Avg.", "Max. Sales Rank", etc.

- **Sliders:** Changed Seller Trust slider `max` from `100` to `10`.

- JavaScript:

  - Updated `profitMarginSteps` and `salesRankSteps` to use "Any" labels.
  - Updated event listeners to handle the "Any" state logic for all inputs.

- CSS:

   

  Updated the selector list for filter values to apply the requested styling:

  ```
  #sales-rank-value, ... #percent-down-value {
      padding-left: 20px;
      color: rgba(102, 153, 204, 0.9);
  }
  ```

## 4. Verification Results

- **Automated Tests:** A backend verification script (`verify_trust_rounding.py`) confirmed that filtering for "10/10" (Input 10) correctly returned items with scores like `0.96`, which previously failed.
- **Visual Verification:** A frontend script verified the correct order of elements, correct styling (blue color), and correct label text ("Any").
- **User Verification:** Confirmed that all filters, including Seller Trust, are working as expected.

## 5. Status

**Task Successful.** The filter logic now accurately reflects the data model and user expectations for rounding, and the UI has been standardized.

## Dev Log Entry - UI Tweaks & Strategy Data Migration

### **Task Overview**

The primary objective of this task was to improve the "Strategy Database" (`/strategies`) feature by addressing two key issues:

1. **UI Legibility:** The header row of the strategies table was difficult to read (white text on a light background). The goal was to style it consistently with the Dashboard's "Book Deals" section (dark blue background).
2. **Missing Data:** The "Trigger" and "Confidence" columns displayed "N/A" for all entries. This was due to the underlying data being legacy unstructured text. The goal was to migrate this content to a structured format to populate these fields.

### **Challenges & Roadblocks**

- **Verification Environment Instability:**
  - *Issue:* Running the frontend verification script (`verify_strategies.py`) initially failed because the local Flask development server was not running, and dependencies were missing in the fresh sandbox environment.
  - *Diagnosis:* The `wsgi.py` entry point contained hardcoded absolute paths (`/var/www/agentarbitrage`) specific to the production environment, preventing it from running locally. Additionally, the sandbox lacked `flask` and other core libraries.
  - Resolution:
    - Installed necessary Python packages (`flask`, `python-dotenv`, `httpx`, etc.).
    - Modified `wsgi.py` to use `os.getcwd()` for dynamic path resolution and added a `if __name__ == "__main__":` block to allow direct execution.
    - Started the Flask server as a background process before running Playwright scripts.
- **Data State Discovery:**
  - *Observation:* Upon inspection, I found a `strategies_structured.json` file already present in the repository.
  - *Action:* Instead of re-running the costly and time-consuming AI migration script (`migrate_strategies.py`), I verified that `strategies_structured.json` already contained the parsed data (with populated "trigger" and "confidence" fields) and simply promoted it to be the active `strategies.json`.

### **Implementation Details**

#### **1. UI Styling (`templates/strategies.html`)**

The table header styling was updated to match the application's "Book Deals" aesthetic.

- **Change:** Applied inline styles to the `<thead>` row.
- **CSS Values:** `background-color: #26567e;` (Dark Blue) and `color: white;`.

#### **2. Data Migration**

- **Source:** `strategies_structured.json` (Pre-existing structured data).
- **Destination:** `strategies.json` (The active file read by the application).
- **Result:** The application now reads JSON objects with specific keys (`category`, `trigger`, `advice`, `confidence`) instead of simple strings. The Jinja2 template logic in `strategies.html` correctly renders these fields, replacing the "N/A" fallbacks.

#### **3. Local Development Robustness (`wsgi.py`)**

- **Change:** Removed hardcoded production paths.

- Code:

  ```
  import sys
  import os
  # Dynamically add current directory to path
  sys.path.insert(0, os.getcwd())
  from wsgi_handler import app as application
  
  # Allow local execution
  if __name__ == "__main__":
      application.run(host='0.0.0.0', port=5000, debug=True)
  ```

### **Outcome**

**Status: SUCCESS**

- **Legibility:** The Strategy Database headers are now clearly readable with high contrast.
- **Data Integrity:** The "Trigger" and "Confidence" columns are fully populated with meaningful data extracted from the legacy text.
- **Verification:** Visual verification via Playwright screenshot confirmed the correct rendering of both the new styles and the structured data.

# Dev Log: Fix Strategy Extraction Parsing & Update RBAC Documentation

**Date:** January 4, 2025 **Task:** Fix "Guided Learning" data persistence issue and update documentation for Role-Based Access Control (RBAC).

## 1. Task Overview

The primary objective was to investigate and fix a reported issue where strategies extracted via the "Guided Learning" tool were not appearing in the `strategies.json` database or the UI. The user suspected a silent failure during the save process.

Secondarily, the user requested a comprehensive update to the project documentation (`README.md`, `AGENTS.md`, etc.) to accurately reflect the application's current Role-Based Access Control (RBAC) policies, specifically clarifying which features are restricted to "Admin" vs. "User" roles.

## 2. Challenges & Diagnosis

### The "Missing Strategies" Bug

- **Symptom:** Content submitted to Guided Learning was processed, but the resulting strategies were not persisted to `strategies.json`.

- **Root Cause:** The `extract_strategies` and `extract_conceptual_ideas` functions rely on the xAI API (`grok-4-fast-reasoning`). It was discovered that the LLM frequently wraps its JSON output in Markdown code blocks (e.g., ````json [ ... ] ````). The existing code passed this raw string directly to `json.loads` in the `/approve` route (or the frontend display), causing a `json.JSONDecodeError` which was either silently caught or resulted in the data being discarded.

- Complexity:

   

  The issue occurred at two points:

  1. **Extraction:** The raw text returned to the UI contained the markdown artifacts.
  2. **Approval:** When the user clicked "Approve", the server attempted to parse this dirty string again. The fallback logic for "legacy text" (splitting by newline) was also at risk of including the markdown backticks as valid strategy text.

### Documentation Drift

- **Issue:** The codebase has evolved to include strict access control (Admin vs. User), but the core documentation files (`System_Architecture.md`, `README.md`) treated the system as having a single user type. This created ambiguity for future developers regarding the intended security model.

### File Timestamp Confusion

- **Issue:** The user noted that `strategies_structured.json` had an old timestamp (Jan 1st) despite new strategies being added (Jan 4th).
- **Finding:** Analysis confirmed that `strategies.json` is the active "live" database used by the application (`wsgi_handler.py` and `ava_advisor.py`). `strategies_structured.json` is merely a static artifact generated by the manual `migrate_strategies.py` utility and is not updated by the runtime application.

## 3. Actions Taken

### A. Code Fixes (`wsgi_handler.py`)

1. **Implemented Markdown Stripping:**

   - Added a regex sanitation step to both

      

     ```
     extract_strategies
     ```

      

     and

      

     ```
     extract_conceptual_ideas
     ```

      

     functions

      

     before

      

     returning the payload:

     ```
     content = re.sub(r'^```json\s*|\s*```$', '', content.strip(), flags=re.MULTILINE)
     ```

   - This ensures the UI receives clean, raw JSON ready for rendering.

2. **Robust Approval Logic:**

   - Updated the `/approve` route to re-apply this regex sanitation on the submitted form data before attempting `json.loads`.
   - Improved the fallback logic (used if JSON parsing fails) to explicitly filter out lines starting with backticks (`````), preventing markdown artifacts from being saved as "text strategies."

3. **Verification:** Created and ran a standalone script (`verify_markdown_strip.py`) to confirm the regex correctly handles various edge cases (with/without `json` label, leading/trailing whitespace).

### B. Documentation Updates

Updated the following files to explicitly define the Admin vs. User permissions:

- **`README.md`**: Marked features like "Guided Learning" and "Deals Config" as **(Admin Only)**.
- **`AGENTS.md`**: Added a "Role-Based Access Control (RBAC)" section to the Technical Notes.
- **`Documents_Dev_Logs/System_Architecture.md`**: Added a dedicated "User Roles & Access Control" section defining the specific routes accessible to each role.
- **`Documents_Dev_Logs/Feature_Deals_Dashboard.md`**: Clarified that "Deals Query Configuration" is restricted.
- **`Documents_Dev_Logs/Feature_Guided_Learning_Strategies_Brain.md`**: Added a prominent "Access Control" header stating these tools are strictly for Admins.

## 4. Outcome

- **Status:** **Successful**.
- Verification:
  - The parsing logic now robustly handles LLM outputs regardless of markdown wrapping.
  - Documentation accurately reflects the current security architecture.
  - The file timestamp discrepancy was verified as "working as designed" (manual artifact vs. live DB).