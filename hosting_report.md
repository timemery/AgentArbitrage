# Application Performance & Capacity Report

## Executive Summary

**Infrastructure:** Hostinger VPS KVM 1 (1 vCPU, 4GB RAM)
**Web Server:** Apache + mod_wsgi (`processes=2`, `threads=5` => **Max 10 Concurrent Requests**)
**Background Worker:** Celery (1 Worker Process)
**Database:** SQLite (WAL Mode)

**Constraint Warning:**
Your primary bottleneck is the **1 vCPU limit** shared between the heavy background ingestion process (Smart Ingestor) and the web server. Additionally, the **synchronous nature** of the AI features means a single user asking for advice blocks 1 of your 10 available server threads for 3-10 seconds.

---

## 1. User-Facing Endpoints Analysis

### Group A: Light (High Concurrency Capable)
*Fast, low-CPU operations. Mostly static serves or simple DB reads.*

| Endpoint | Auth | Sync/Async | Workload | External APIs | Cache |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`GET /` (Index)** | Public | Sync | Render Template | None | Browser |
| **`GET /login`** | Public | Sync | Render Template | None | Browser |
| **`POST /login`** | Public | Sync | DB Read (Users) | None | None |
| **`GET /dashboard`** | User | Sync | Render Template | None | Browser |
| **`GET /settings`** | User | Sync | Read JSON | None | None |
| **`GET /results`** | Admin | Sync | Read Session/Temp | None | None |
| **`GET /strategies`** | Admin | Sync | Read JSON | None | None |
| **`GET /intelligence`** | Admin | Sync | Read JSON | None | None |
| **`GET /data_sourcing`** | Admin | Sync | Read JSON | None | None |
| **`GET /scan-status`** | Admin | Sync | Read JSON | None | None |
| **`GET /download/*`** | User | Sync | Serve Static File | None | Browser |

### Group B: Medium (Moderate Load)
*Complex DB queries or data processing. Can slow down under load.*

| Endpoint | Auth | Sync/Async | Workload | External APIs | Cache |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`GET /api/deals`** | User | Sync | **Heavy DB Read.** Complex SQL with multiple filters and joins. Pagination limits rows, but `COUNT(*)` scans index. | None | DB Cache (SQLite) |
| **`GET /api/deal-count`** | User | Sync | **Heavy DB Read.** Same complex query as deals, `COUNT(*)` only. Polls every 30-60s per user. | None | DB Cache (SQLite) |
| **`POST /settings`** | User | Async | Write JSON + **Triggers Celery Task** (`recalculate_deals`). | None | None |
| **`POST /api/run-janitor`**| User | Sync | DB Write (Delete). Locks DB briefly. | None | None |
| **`POST /approve`** | Admin | Sync | Write JSON (Strategies). | None | None |
| **`POST /api/remove-duplicates/*`** | Admin | Sync | CPU (JSON Parsing). | None | None |
| **`GET /amazon_callback`** | User | Sync | **HTTP Request.** Exchanges OAuth code for token. | Amazon Auth | None |

### Group C: Heavy (The Bottlenecks)
*Blocking operations that consume threads for seconds or use significant CPU.*

| Endpoint | Auth | Sync/Async | Workload | External APIs | Cache |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`GET /api/ava-advice/<asin>`** | User | **Sync** | **Blocking.** Waits for AI response. | **xAI (`grok-4-fast-reasoning`)**<br>Latency: 3-8s | None |
| **`POST /api/mentor-chat`** | User | **Sync** | **Blocking.** Waits for AI response. | **xAI (`grok-4-fast-reasoning`)**<br>Latency: 3-8s | None |
| **`POST /learn`** | Admin | **Sync** | **Very Heavy.** Scrapes URL + 2 Parallel AI Calls. | **xAI (x2)** + **BrightData**<br>Latency: 10-30s | None |
| **`GET /api/debug/deal/<asin>`** | User | **Sync** | **Blocking.** Live fetch from Keepa. | **Keepa API**<br>Latency: 1-3s | None |
| **`POST /trigger_restriction_check`** | User | Async | Enqueues heavy Celery task. | None (Task does API) | None |

---

## 2. Infrastructure Bottlenecks

### 1. The 10-Thread Limit (Hard Cap)
Your Apache configuration (`processes=2`, `threads=5`) allows for exactly **10 concurrent requests**.
*   **Scenario:** If 10 users click "Ask Mentor" at the same time, the 11th user receives a generic loading spinner or timeout because all 10 threads are blocked waiting for xAI to respond.

### 2. The Single vCPU (Resource Contention)
The **Smart Ingestor** (Celery) runs continuously on the same CPU.
*   **Impact:** When the Ingestor is processing a batch of 50 deals (parsing JSON, calculating math), it spikes CPU usage. This directly slows down the Web Server's ability to render templates or run SQL queries for the Dashboard.
*   **Risk:** During a "Heavy Commit" phase (batching 5 items with full history), web response times (`/api/deals`) may degrade significantly (p95 > 2s).

### 3. Database Locking
SQLite in WAL mode handles concurrency well, but heavy write bursts from the Ingestor (upserting 50 deals) can momentarily slow down complex read queries from the Dashboard (`/api/deals`).

---

## 3. Concurrency Estimates

### Scenario A: Passive Browsing (Light/Medium)
*   **User Action:** Scrolling the dashboard, applying filters.
*   **Load:** Frequent calls to `/api/deals` and `/api/deal-count`.
*   **Capacity:** **15-20 Concurrent Users**.
    *   *Constraint:* CPU (DB Queries) vs Ingestor.

### Scenario B: AI Power Users (Heavy)
*   **User Action:** Chatting with Mentor, clicking "Advice" on every deal.
*   **Load:** Frequent blocking calls to `/api/ava-advice`.
*   **Capacity:** **3-5 Concurrent Users**.
    *   *Constraint:* Thread Exhaustion. 5 users asking for advice simultaneously consume 50% of your server capacity.

### Recommended Target
**8 Concurrent Users**
*   *Mix:* 6 Browsing, 2 using AI features.
*   This keeps p95 latency acceptable (< 1s for browsing, < 5s for AI).

---

## 4. Proposed Load Test Plan

**Tool:** [Locust](https://locust.io/) (Python-based load testing tool)

### Test Scenarios

#### 1. The "Browser" (70% of users)
*   **Behavior:**
    *   Logs in.
    *   Loads Dashboard.
    *   Polls `/api/deal-count` every 30s.
    *   Fetches `/api/deals` with random filters every 10-20s.
    *   Downloads a random image occasionally.

#### 2. The "Analyst" (25% of users)
*   **Behavior:**
    *   Same as Browser.
    *   Expands a deal details row every 60s (triggers `/api/ava-advice`).
    *   *Note:* This tests the thread blocking impact.

#### 3. The "Learner" (5% of users - Admin only simulation)
*   **Behavior:**
    *   Hits `/strategies` and `/intelligence`.
    *   Submits a URL to `/learn` (Very heavy).

### Ramp-Up Plan
*   **Phase 1 (Baseline):** 1 User. Verify 0 errors.
*   **Phase 2 (Ramp):** Spawn 1 user every 5 seconds.
*   **Target:** 10 Users.
*   **Duration:** 5 Minutes.
*   **Success Criteria:**
    *   No 50x Errors.
    *   `/api/deals` p95 < 800ms.
    *   `/api/ava-advice` p95 < 6000ms.

### Execution Command (Example)
```bash
# Install Locust
pip install locust

# Create locustfile.py (see below)
# Run headless
locust -f locustfile.py --headless -u 10 -r 1 --run-time 5m --host https://agentarbitrage.co
```

### Sample `locustfile.py` Structure
```python
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(5, 15)

    def on_start(self):
        self.client.post("/login", {"username": "tester", "password": "..."})

    @task(3)
    def view_dashboard(self):
        self.client.get("/api/deals?page=1&limit=50")

    @task(1)
    def check_advice(self):
        # Pick a known ASIN or random one if possible
        self.client.get("/api/ava-advice/0123456789")
```
