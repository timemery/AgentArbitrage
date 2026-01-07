### Task Description: Implement XAI Token Management and Caching

**Objective:** To control XAI API costs and improve performance by creating a configurable token management system and a persistent caching mechanism for API responses.

**Key Components:**

1.  **XAI Token Manager:** A new class to manage the daily quota of XAI API calls.
2.  **Persistent Cache:** A system to store and retrieve XAI API responses, avoiding redundant calls.
3.  **Configuration:** New settings in `settings.json` to control the token manager.
4.  **Integration:** Modify existing code to use the new token manager and cache.

---

### Detailed Plan

#### 1. Create the `XaiTokenManager`

*   **Create a new file:** `keepa_deals/xai_token_manager.py`.
*   **Implement the `XaiTokenManager` class with the following features:**
    *   **Initialization (`__init__`):**
        *   Takes the daily call limit from the settings.
        *   Loads the current call count and the last reset date from a persistent state file (e.g., `xai_token_state.json`).
        *   If the last reset date is not today, it resets the call count to 0 and updates the date.
    *   **`request_permission()` method:**
        *   Checks if the current call count is less than the daily limit.
        *   If permission is granted, it increments the call count and saves the.
        *   If the limit is exceeded, it returns `False` and logs a warning.
    *   **`save_state()` and `load_state()` methods:**
        *   Private methods to handle the reading and writing of the `xai_token_state.json` file. This file will store `{'last_reset_date': 'YYYY-MM-DD', 'calls_today': <count>}`.

#### 2. Implement the Persistent Cache

*   **Create a new file:** `keepa_deals/xai_cache.py`.
*   **Implement the `XaiCache` class:**
    *   **Initialization (`__init__`):**
        *   Loads the cache from a JSON file (e.g., `xai_cache.json`) into a dictionary in memory.
    *   **`get(key)` method:**
        *   Returns the cached response for the given key, or `None` if not found.
    *   **`set(key, value)` method:**
        *   Adds a new response to the in-memory cache and saves the entire cache to the JSON file.
    *   **Cache Key Strategy:**
        *   The cache key should be a unique identifier for the request. For seasonality, a good key would be a combination of the book's title, categories, and manufacturer. For the reasonableness check, it would be the title, category, and price.

#### 3. Update Configuration

*   **Modify `settings.json`:**
    *   Add a new key-value pair: `"max_xai_calls_per_day": 1000`. This will be the default daily limit.

#### 4. Integrate the New Systems

*   **Modify `keepa_deals/seasonality_classifier.py`:**
    *   In the `_query_xai_for_seasonality` function:
        *   Instantiate the `XaiCache`.
        *   Create a unique cache key from the function's arguments.
        *   Check the cache for an existing response before making an API call.
        *   If a cached response exists, return it.
        *   If not, instantiate the `XaiTokenManager`.
        *   Call `xai_token_manager.request_permission()`.
        *   If permission is denied, log it and return a default value (e.g., "Year-round").
        *   If permission is granted, proceed with the API call.
        *   After a successful API call, store the result in the cache.
*   **Modify `keepa_deals/stable_calculations.py`:**
    *   In the `_query_xai_for_reasonableness` function:
        *   Follow the same integration pattern as in `seasonality_classifier.py`:
            *   Instantiate the cache and create a key.
            *   Check the cache first.
            *   If not cached, request permission from the token manager.
            *   If permission is granted, make the API call.
            *   Cache the result.
            *   If permission is denied, return a default value (e.g., `True` for "reasonable").

---

### Guide for the Implementing Agent

*   **Start with a fresh, high-performance sandbox.** This is crucial to avoid environmental instability.
*   **Create the new modules first:** `xai_token_manager.py` and `xai_cache.py`. You can test them in isolation before integrating them.
*   **Be mindful of file I/O:** The cache and token manager state files will be written to frequently. Ensure the implementation is robust and handles potential file access errors gracefully.
*   **Logging is key:** Add detailed logging to the new modules to track token usage and cache hits/misses. This will be invaluable for debugging.
*   **No regressions:** The application should continue to function as before if the new systems are not enabled or if the daily limit is set to a very high number. The default behavior should be to allow the API calls.
*   **Testing:** Since there is no formal test suite, manual testing will be required. A good approach would be to:
    1.  Lower the `max_xai_calls_per_day` to a small number (e.g., 5).
    2.  Run a process that triggers more than 5 XAI calls.
    3.  Verify from the logs that only 5 calls were made and the rest were denied.
    4.  Check the `xai_cache.json` file to ensure that the successful calls were cached.
    5.  Run the process again and verify from the logs that the cached results are being used and no new API calls are made.
