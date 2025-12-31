# Token Management Strategy

This document consolidates the API token management strategies for the three core external services: Keepa, XAI, and Amazon SP-API. These strategies are critical for maintaining system stability and controlling costs.

---

## 1. Keepa API: "Controlled Deficit" Optimization

**Strategy:** Aggressive consumption above a threshold, quick recovery below it.
**Implementation:** `keepa_deals/token_manager.py` (and logic in `backfiller.py`, `simple_task.py`)

### The "Why"
Keepa's API allows the token balance to go negative (deficit spending) as long as the starting balance is positive. A strict "no deficit" policy (waiting until we have *enough* tokens for a batch) causes massive delays. The "Controlled Deficit" strategy maximizes throughput by leveraging this allowance.

### The Algorithm
1.  **Threshold Check:** Defined `MIN_TOKEN_THRESHOLD` (50 tokens).
2.  **Aggressive Phase:** If `current_tokens > 50`, the system **allows** the request to proceed immediately, even if the estimated cost exceeds the current balance.
    *   *Example:* Balance 55, Cost 80 -> **Approved**. (Resulting balance: -25).
3.  **Recovery Phase:** If `current_tokens < 50` (or negative), the system pauses.
    *   **Crucial Optimization:** It waits only until the balance recovers to `50 + 5` (approx 55). It does **not** wait for a full refill (300).
    *   *Benefit:* Wait times reduced from ~18 minutes (full refill) to <2 minutes (recovery).

### Task-Specific Buffers
*   **Backfiller:** Uses the standard strategy.
*   **Upserter (`simple_task.py`):** Requires a stricter **20 token buffer** to ensure it doesn't starve the backfiller or trigger a lock-out during critical updates.

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
*   **Note:** This feature calls the xAI API directly (via `httpx`) and **does not** currently utilize the `XaiTokenManager` or the daily quota system. This is acceptable because it is a manual, Admin-triggered action, not an automated loop.

---

## 3. Amazon SP-API: LWA-Only Authentication

**Strategy:** Persistent, offline access using Refresh Tokens without AWS IAM complexity.
**Implementation:** `keepa_deals/amazon_sp_api.py`, `keepa_deals/sp_api_tasks.py`

### The "Why"
Modern Private Applications on Amazon SP-API (registered after Oct 2023) generally do not require AWS Signature Version 4 (SigV4) signing with IAM credentials. They rely solely on the **Login with Amazon (LWA)** Access Token. Removing the SigV4 requirement simplifies the architecture and eliminates `403 Forbidden` errors caused by IAM misconfiguration.

### Workflow
1.  **Initial Auth:**
    -   User authorizes the app in Seller Central.
    -   A **Refresh Token** is generated (manually or via OAuth).
2.  **Storage:**
    -   The `refresh_token`, `client_id`, and `client_secret` are stored securely (Env vars or DB).
3.  **Task Execution (Restriction Check):**
    -   **Token Refresh:** The system exchanges the Refresh Token for a short-lived `access_token` (valid for 1h).
    -   **API Call:** The `access_token` is passed in the `x-amz-access-token` HTTP header.
    -   **No Signing:** No AWS `AccessKey`/`SecretKey` is used or required.

### Environment Handling
*   **Sandbox vs. Production:** The system automatically detects if the token is valid for Sandbox or Production by probing the endpoints.
*   **Fallback:** If a Production call fails with 403, it logs the error but does not crash the worker.
