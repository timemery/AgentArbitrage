# Token Management Strategy

This document consolidates the API token management strategies for the three core external services: Keepa, XAI, and Amazon SP-API. These strategies are critical for maintaining system stability and controlling costs.

---

## 1. Keepa API: "Controlled Deficit" Optimization

**Strategy:** Aggressive consumption above a threshold, quick recovery below it.
**Implementation:** `keepa_deals/token_manager.py` (Distributed Token Bucket via Redis)

### The "Why"
Keepa's API allows the token balance to go negative (deficit spending) as long as the starting balance is positive. A strict "no deficit" policy causes massive delays. The "Controlled Deficit" strategy maximizes throughput by leveraging this allowance. To handle multiple concurrent workers (Backfiller + Upserter) without race conditions, the system uses a **Shared Redis State**.

### Dynamic Rate Adaptation
The `TokenManager` dynamically updates its `REFILL_RATE_PER_MINUTE` from the `refillRate` field in Keepa API responses.
*   **Default:** Starts with a conservative guess (e.g., 5/min).
*   **Adaptation:** Upon the first API sync, it learns the true rate (e.g., 20/min for upgraded plans).
*   **Benefit:** Users who upgrade their Keepa plan immediately see faster processing without code changes.

### The Algorithm (Distributed & Float-Safe)
Since Keepa tokens are floating-point numbers (e.g., 54.5), and multiple workers compete for them, the system uses an **Optimistic Locking** strategy with Redis `incrbyfloat`:

1.  **Atomic Reservation:** The worker unconditionally decrements the shared Redis counter (`incrbyfloat -cost`).
2.  **Threshold Check:** It reads the new balance.
3.  **Aggressive Phase:** If `new_balance > MIN_TOKEN_THRESHOLD` (20) OR `old_balance` was sufficient to start, it proceeds. The deficit is allowed.
4.  **Recharge Mode (Low Rate Protection):** If the Keepa refill rate is < 10/min AND the balance drops below the threshold (20), the system enters **Recharge Mode**.
    *   **Action:** All requests are blocked.
    *   **Exit Condition:** Wait until tokens reach the `BURST_THRESHOLD` (280) to allow a sustained burst of activity. This prevents "starvation loops" where tasks fight over a trickle of tokens.
5.  **Recovery Phase (Revert):** If the reservation drops the balance dangerously low (e.g., below threshold when it was already low) and Recharge Mode is not active:
    *   The worker **Reverts** the transaction (`incrbyfloat +cost`).
    *   It enters a **Sleep Loop**, waiting for the balance to recover to `Threshold + Cost + Buffer` (e.g., 25 + cost).

### Resilience & Crash Recovery (Zombie Locks)
To prevent "Zombie Locks" (stale locks persisting after a crash or deployment), the system employs a "Redis Flush" strategy during shutdown:
*   **Script:** `Diagnostics/kill_redis_safely.py` (invoked by `kill_everything_force.sh`).
*   **Action:** Connects to Redis, executes `FLUSHALL` (clears memory), then `SAVE` (forces disk sync).
*   **Result:** This ensures that when the system restarts, the token state and locks are completely reset, preventing "Task already running" errors.

### Task-Specific Buffers
*   **Backfiller:**
    *   **Dynamic Batching:** Default batch size is 20. If refill rate < 20/min, batch size is automatically reduced to **1 ASIN** to allow incremental progress without hitting timeouts.
*   **Upserter (`simple_task.py`):**
    *   **Frequency:** Scheduled every **15 minutes** (down from 1 min) to allow tokens to accumulate for other tasks.
    *   **Batch Size:** Reduced to **2 ASINs** (or **1** if refill rate < 20/min) to prevent monopolizing the token bucket.
    *   **Blocking Wait:** Uses `token_manager.request_permission_for_call()` to block and wait for sufficient tokens instead of skipping the run.
*   **API Wrapper (`keepa_api.py`):**
    *   **Rate Limit Protection:** Functions like `fetch_deals_for_deals` accept an optional `token_manager` argument.
    *   **Behavior:** If provided, the wrapper calls `request_permission_for_call` *before* the API request. This enforces a blocking wait if tokens are low, preventing `429 Too Many Requests` errors during high-frequency ingestion loops.

---

## 2. XAI API: Quotas & Model Selection

**Strategy:** Strict daily cap with aggressive local caching, utilizing the `grok-4-fast-reasoning` model for high-speed analysis.
**Implementation:** `keepa_deals/xai_token_manager.py`, `keepa_deals/xai_cache.py`, and `keepa_deals/ava_advisor.py`

### Model Selection
*   **Primary Model:** `grok-4-fast-reasoning`
*   **Use Cases:** Seasonality Classification, "List at" Price Reasonableness Check, Strategy Extraction, and "Advice from Ava".
*   **Why:** Provides the best balance of reasoning capability and speed for real-time and batch processing.

### Cost Control Mechanism
1.  **Daily Quota:**
    -   A JSON state file (`xai_token_state.json`) tracks `calls_today` and `last_reset_date`.
    -   Before any automated API call (e.g., price check), the manager checks if `calls_today < daily_limit` (default: 1000).
    -   If the limit is reached, the request is denied, and the system falls back to a default "Safe" assumption (e.g., assuming a price is reasonable to avoid rejecting valid deals).
2.  **Caching (`XaiCache`):**
    -   Results are cached in a local dictionary/JSON file.
    -   **Cache Key:** Composite key of `Title | Category | Season | Price`.
    -   **Hit:** If the key exists, the cached boolean result is returned immediately (0 cost).
    -   **Miss:** If not in cache and quota allows, the API is called, and the result is saved.

### Exception: Admin Features
*   **Features:** Guided Learning (`/learn`) and "Advice from Ava" (`/api/ava-advice`).
*   **Policy:** These features operate on-demand (user-triggered) and currently bypass the strict daily quota limits managed by `XaiTokenManager`, though they still consume the underlying API credit.

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
    -   The `refresh_token`, `client_id`, and `client_secret` are stored securely (Env vars or DB `user_credentials` table).
3.  **Task Execution (Restriction Check):**
    -   **Token Refresh:** The system exchanges the Refresh Token for a short-lived `access_token` (valid for 1h).
    -   **API Call:** The `access_token` is passed in the `x-amz-access-token` HTTP header.
    -   **No Signing:** No AWS `AccessKey`/`SecretKey` is used or required.
    -   **Restriction Logic:** Calls `getListingsRestrictions` with the specific `conditionType` (e.g., `used_like_new`) to ensure accurate gating status.

### Environment Handling
*   **Sandbox vs. Production:** The system automatically detects if the token is valid for Sandbox or Production by probing the endpoints.
*   **Fallback:** If a Production call fails with 403, it logs the error but does not crash the worker. Items are marked with an error state (-1) in the `user_restrictions` table.
