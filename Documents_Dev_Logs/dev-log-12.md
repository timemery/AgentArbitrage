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