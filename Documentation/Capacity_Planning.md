# Capacity Planning & Scalability Roadmap

**Version:** 1.2 (Feb 2026)
**Infrastructure:** Hostinger VPS KVM 1 (1 vCPU, 4GB RAM)
**Architecture:** Flask + Celery + SQLite (WAL) + Redis

## 1. Executive Summary
This document serves as the strategic guide for scaling "Agent Arbitrage" from its current pre-launch state to 10,000+ subscribers. It maps subscriber growth to specific hardware requirements and architectural changes, ensuring predictable costs and performance.

### Current Baseline (KVM 1)
*   **Max Concurrent Users:** ~10-15 (Browsing Only), ~3-5 (Heavy AI Usage).
*   **Primary Bottleneck:** Single vCPU shared between Background Ingestion and Web Server.
*   **Secondary Bottleneck:** Synchronous AI calls blocking web server threads (Max 10 threads).

### Baseline Performance Verification (Load Test)
*   **Date:** Feb 16, 2026
*   **Target:** Homepage (`/`)
*   **Result:** **295 Requests/sec** at 20 concurrency.
*   **Latency:** p95 **137ms**.
*   **Conclusion:** The Apache/WSGI setup is healthy for static/light content. The bottleneck is strictly CPU-bound application logic (Ingestion) and external API blocking.

---

## 2. Endpoint Analysis & Resource Usage

To accurately plan for growth, we must understand the resource cost of specific user actions.

### Group A: Light (Browsing)
*Fast, low-CPU operations. Mostly static serves or simple DB reads.*

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

## 3. Growth Tiers & Upgrade Triggers

### Tier 1: Launch Phase (Current)
*   **Subscribers:** 0 - 200
*   **Concurrent Users:** 1 - 10
*   **Infrastructure:** KVM 1 (1 vCPU / 4GB RAM) - $6/mo
*   **Required Optimizations:**
    *   [x] **SQLite WAL Mode:** Enabled. Handles concurrency well.
    *   [ ] **Celery Priority:** Set `Nice=19` to deprioritize ingestion spikes.
    *   [ ] **Compression:** Enable Brotli/Gzip in Apache.
    *   [ ] **HTTP/2:** Enable `mod_http2` in Apache.
*   **Status:** **Adequate.** The current server handles this load if optimized.

### Tier 2: Growth Phase
*   **Subscribers:** 200 - 1,000
*   **Concurrent Users:** 10 - 50
*   **Infrastructure:** Upgrade to **KVM 4** (4 vCPU / 16GB RAM) - ~$25/mo
*   **Why Upgrade?**
    *   The single vCPU will be saturated by the Ingestor alone.
    *   Web traffic needs dedicated cores.
*   **Architectural Changes:**
    *   **Worker Separation:** Pin Celery to Cores 3-4, Web to Cores 1-2.
    *   **WSGI Tuning:** Increase to `processes=4 threads=10` (40 threads) to absorb blocking AI calls.

### Tier 3: Scale Phase
*   **Subscribers:** 1,000 - 5,000
*   **Concurrent Users:** 50 - 250
*   **Infrastructure:** Split Services (Total ~$80-100/mo)
    *   **Web Server:** KVM 4 (Dedicated to Flask).
    *   **Worker Server:** KVM 4 (Dedicated to Celery/Ingestion).
    *   **Database:** Managed SQL (PostgreSQL) or Dedicated DB VPS.
*   **Architectural Changes:**
    *   **Async AI:** Move "Get Advice" calls to a background task queue (Celery) + WebSocket/Polling frontend. This removes the 10-thread hard limit.
    *   **Migration:** Move from SQLite to PostgreSQL to handle heavy concurrent writes/reads without locking.

### Tier 4: Enterprise (Competitor Level)
*   **Subscribers:** 5,000+
*   **Concurrent Users:** 250+
*   **Infrastructure:** Load Balancer + Multiple Web Nodes.

---

## 4. Immediate Optimization Plan (The "To-Do")

Based on host feedback, these are the low-hanging fruits to maximize KVM 1.

### A. Tuning Apache (Host Recommended)
The host noted that `WSGIDaemonProcess` might be missing.
*   **Status:** *Investigation shows it IS present in the repository's `agentarbitrage.conf`.*
*   **Action:** Verify if the live server is actually using this config file or a default one. Run `apache2ctl -S` on the VPS to check enabled sites.
*   **Config:** Current `processes=2 threads=5` is conservative. On KVM 1, we could try `processes=2 threads=10` to allow more waiting slots for AI calls, *if* RAM permits.

### B. Compressions & Caching
Reduce bandwidth and speed up page loads.
*   **Action:** Enable `mod_deflate` (Gzip) and `mod_brotli`.
*   **Action:** Add `Cache-Control` headers for static assets (CSS/JS/Images) to 1 year.

### C. Process Priority
Prevent the "Site Stuck" feeling during ingestion.
*   **Action:** Modify `celery.service` to include `Nice=19` and `CPUSchedulingPolicy=idle`.

---

## 5. Proposed Load Test Plan (Locust)

Use this plan to validate capacity before upgrading tiers.

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
