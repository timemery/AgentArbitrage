# Token Management Strategy

This document consolidates the API token management strategies for the three core external services: Keepa, XAI, and Amazon SP-API. These strategies are critical for maintaining system stability and controlling costs.

---

## 1. Keepa API: "Controlled Deficit"

**Strategy:** Allow the token balance to go negative, then wait for a refill.
**Implementation:** `keepa_deals/token_manager.py` (and logic in `backfiller.py`)

### The "Why"
Keepa's API bucket mechanism allows bursts of requests that can drive the token balance into negative figures. Rather than throttling *every* request to stay positive (which is slow), we allow the scraper to consume tokens aggressively until the bucket is empty. When the balance hits 0 (or the estimated cost of the next batch exceeds the balance), the system pauses execution for a calculated duration to allow the bucket to refill to a safe level.

### Key Parameters
-   **Refill Rate:** ~5 tokens / minute.
-   **Cost Estimation:**
    -   Base cost: 1 token per product (often waived if `offers` parameter is used).
    -   `offers` parameter: Expensive. Increases cost significantly (e.g., +6-12 tokens) depending on the number of offer pages.
-   **Wait Logic:** If `tokens_available < estimated_cost`, calculate `wait_time = (deficit / refill_rate)`. The process sleeps for this duration.

---

## 2. XAI API: Local Cache & Daily Quota

**Strategy:** Strict daily cap with aggressive local caching to minimize costs.
**Implementation:** `keepa_deals/xai_token_manager.py` and `keepa_deals/xai_cache.py`

### The "Why"
The XAI API (Grok) incurs a direct financial cost per token generated. To prevent runaway bills, we enforce a strict daily limit on the number of calls. Additionally, many AI judgments (e.g., "Is 'Biology 101' a textbook?") are repetitive. Caching these results prevents redundant calls for the same book/season/price combination.

### Mechanism
1.  **Daily Quota:**
    -   A JSON state file (`xai_token_state.json`) tracks `calls_today` and `last_reset_date`.
    -   Before any API call, the manager checks if `calls_today < daily_limit` (default: 1000).
    -   If the limit is reached, the request is denied, and the system falls back to a default "Safe" assumption (e.g., assuming a price is reasonable).
2.  **Caching (`XaiCache`):**
    -   Results are cached in a local dictionary/JSON file.
    -   **Cache Key:** Composite key of `Title | Category | Season | Price`.
    -   **Hit:** If the key exists, the cached boolean result is returned immediately (0 cost).
    -   **Miss:** If not in cache and quota allows, the API is called, and the result is saved.

### Exception: Guided Learning
*   **Route:** `/learn`
*   **Implementation:** `wsgi_handler.py` -> `query_xai_api`
*   **Note:** This feature calls the xAI API directly (via `httpx`) and **does not** currently utilize the `XaiTokenManager` or the daily quota system. This is acceptable because it is a manual, user-triggered action, not an automated loop.

---

## 3. Amazon SP-API: OAuth 2.0 Refresh Flow

**Strategy:** Persistent, offline access using Refresh Tokens.
**Implementation:** `keepa_deals/sp_api_tasks.py` and `wsgi_handler.py`

### The "Why"
The Amazon Selling Partner API (SP-API) requires secure OAuth 2.0 authentication. Access tokens are short-lived (1 hour). To allow background tasks (like checking restriction status) to run without user intervention, we must securely store and use the long-lived **Refresh Token** to generate new Access Tokens on demand.

### Workflow
1.  **Initial Auth (Frontend):**
    -   User clicks "Connect" -> Redirects to Amazon -> User approves app -> Redirects back with `auth_code`.
    -   Backend exchanges `auth_code` for `access_token` and `refresh_token`.
2.  **Storage:**
    -   The `refresh_token` and `seller_id` are stored (currently in Flask session for the user context, passed as arguments to background tasks).
3.  **Background Task Execution:**
    -   When a Celery task runs (e.g., `check_all_restrictions_for_user`), it receives the `refresh_token` as an argument.
    -   **Refresh Logic:** The task calls `_refresh_sp_api_token(refresh_token)`. This makes a request to Amazon's token endpoint (`api.amazon.com/auth/o2/token`) using the App's Client ID/Secret to get a *new* `access_token`.
    -   This new token is valid for 1 hour and is used for the subsequent API calls (e.g., checking `get_listings_restrictions`).

**Security Note:** The Client Secret is never exposed to the frontend. It is stored in the `.env` file on the server.
