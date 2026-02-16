# Application Performance & Capacity Report (v2)

## Executive Summary

**Infrastructure:** Hostinger VPS KVM 1 (1 vCPU, 4GB RAM)
**Web Server:** Apache + mod_wsgi (`processes=2`, `threads=5` => **Max 10 Concurrent Requests**)
**Background Worker:** Celery (1 Worker Process, CPU-Heavy Ingestion)
**Database:** SQLite (WAL Mode, Shared I/O)

**Critical Bottleneck:** The single vCPU is shared between the **Smart Ingestor** (which parses JSON and calculates complex math for thousands of products) and the **Web Server**. When ingestion runs (every minute), web requests are starved for CPU cycles. Additionally, **synchronous AI calls** block WSGI threads for 5-8 seconds, quickly exhausting the 10-thread limit.

---

## 1. Endpoint Analysis (Detailed)

### Group A: Light (Browsing)
*Static content or simple DB reads. Fast.*

| Endpoint | Auth | Sync/Async | Est. p50 / p95 Latency | External Calls |
| :--- | :--- | :--- | :--- | :--- |
| **`GET /`** | Public | Sync | 20ms / 50ms | None |
| **`GET /login`** | Public | Sync | 30ms / 60ms | None |
| **`GET /dashboard`** | User | Sync | 150ms / 400ms | None |
| **`GET /download/*`** | User | Sync | 50ms / 100ms | None |

### Group B: Medium (Data Filtering)
*Complex SQL queries. CPU-bound during heavy ingestion.*

| Endpoint | Auth | Sync/Async | Est. p50 / p95 Latency | Workload Note |
| :--- | :--- | :--- | :--- | :--- |
| **`GET /api/deals`** | User | Sync | **400ms / 1.5s** | High CPU. Sorts/Filters thousands of rows. Latency spikes when Ingestor is active. |
| **`GET /api/deal-count`** | User | Sync | **200ms / 800ms** | Frequent polling (every 30s). Adds constant background CPU load. |
| **`POST /settings`** | User | Async | 100ms / 200ms | Triggers async Celery task. Fast response. |

### Group C: Heavy (The Bottlenecks)
*Thread-blocking operations. These define your concurrency limit.*

| Endpoint | Auth | Sync/Async | Est. p50 / p95 Latency | External API Constraint |
| :--- | :--- | :--- | :--- | :--- |
| **`GET /api/ava-advice/<asin>`** | User | **Sync** | **5s / 8s** | **Blocks 1 Thread.** Waits for xAI reasoning model. |
| **`POST /api/mentor-chat`** | User | **Sync** | **5s / 8s** | **Blocks 1 Thread.** Waits for xAI reasoning model. |
| **`POST /learn`** | Admin | **Sync** | **15s / 30s** | **Blocks 1 Thread.** Scrapes URL + 2x AI Calls. |
| **`GET /api/debug/deal/<asin>`** | User | **Sync** | **1.5s / 3s** | Blocks 1 Thread. Live Keepa API fetch. |

---

## 2. Actionable Capacity Limits

**Scenario:** Active Ingestion (Background) + Users Browsing & Using AI.

> **Capacity Statement:**
> On KVM 1 (1 vCPU), with the Smart Ingestor running, you can support **~5 concurrent active users** performing **2 Heavy Actions (AI Advice) per minute** before the p95 latency for standard browsing (`/api/deals`) exceeds **2.0 seconds**.

**Why this limit?**
1.  **CPU Starvation:** The Ingestor consumes ~60-80% of the single vCPU during batch processing. This leaves only ~20% for the Web Server to render pages and run SQL, pushing p95 latency up.
2.  **Thread Exhaustion:** With 5 users, if 2 of them click "Get Advice" simultaneously, 20% of your server threads (2/10) are blocked for 8 seconds. If a 3rd user clicks, 30% are blocked. The remaining 7 threads must handle all browsing traffic.

---

## 3. The "Single Best Change" for KVM 1

To raise this limit on the *current hardware*, you must deprioritize the background work to ensure user requests get CPU time.

**Recommendation:** **Apply `nice` to the Celery Worker.**

**The Change:**
Modify the systemd service file for Celery (`/etc/systemd/system/celery.service`) to add:
```ini
[Service]
Nice=19
CPUSchedulingPolicy=idle
```

**The Impact:**
*   This tells the Linux kernel to **only** give CPU time to the Smart Ingestor (Celery) when the Web Server (Apache) is idle.
*   **Result:** Web requests (`/api/deals`) will remain fast (p95 < 800ms) even during heavy ingestion, effectively doubling your "browsing" capacity to **~10-12 users**. The background ingestion will just take slightly longer, which is acceptable.

---

## 4. Proposed Load Test Plan (Locust)

**Objective:** Validate that `Nice=19` prevents web latency spikes during ingestion.

### Configuration
*   **Users:** 10
*   **Spawn Rate:** 1 user every 10s
*   **Duration:** 10 Minutes

### Tasks
1.  **Browsing (High Frequency):** Fetch `/api/deals` (Medium) every 5-10s.
2.  **AI Advice (Low Frequency):** Fetch `/api/ava-advice` (Heavy) every 60s.

### Success Criteria (with `Nice=19`)
*   **Browsing p95:** < 1.0s
*   **AI Advice p95:** < 10.0s (Acceptable for deep reasoning)
*   **Error Rate:** 0%
