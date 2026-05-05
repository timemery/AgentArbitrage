# Dev Log: Hosting Capacity Planning & Diagnostics Tools
**Date:** 2026-02-16
**Author:** Jules (AI Agent)
**Task:** Establish Capacity Planning Baseline & Facilitate Hosting Diagnostics

## Overview
The user needed to provide their hosting provider (Hostinger) with a detailed technical breakdown of the application's resource usage, endpoint latency, and concurrency limits to address performance concerns on a constrained KVM 1 VPS (1 vCPU / 4GB RAM). The host also requested precise diagnostic logs (process snapshots) capturing CPU spikes during the background ingestion window (top of every minute), which proved difficult for the user to time manually.

The goal shifted from purely "answering the host" to creating a permanent **Capacity Planning Roadmap** and a set of **Diagnostic Tools** to empower the user to manage scaling independently.

## Challenges
1.  **Manual Timing Complexity:** The host required running a diagnostic command (`ps ...`) exactly during the 15-second window when the Smart Ingestor runs (XX:00–XX:15). The user struggled to synchronize this manually with UTC server time.
2.  **Resource Contention:** The single vCPU architecture creates a zero-sum game between the background `Smart Ingestor` (CPU-heavy math/parsing) and the Web Server (`mod_wsgi`).
3.  **Host Misconceptions:** The host assumed the application used MySQL (running by default but unused) and that `WSGIDaemonProcess` was missing (despite being in the repo config).
4.  **Information Overload:** The user was overwhelmed by the back-and-forth technical requests from the host regarding specific PIDs, threads, and configuration tuning.

## Solutions Implemented

### 1. Diagnostic Automation Tools
Created two reusable scripts in `Diagnostics/` to eliminate manual error:
*   **`capture_spike.sh`:** Automatically calculates the sleep time required to sync with the next "top of the minute" (XX:55 start for a 25s capture). It runs the exact `ps -eLo` command requested by the host to analyze per-thread CPU usage during the ingest spike.
*   **`optimize_vps.sh`:** Safely stops and disables the unused MySQL/MariaDB services to immediately reclaim ~10% RAM for the application.

### 2. Capacity Planning Documentation
Created `Documentation/Capacity_Planning.md` as a "Living Document" for future scaling. It includes:
*   **Endpoint Analysis:** Categorized all routes into Light (Browsing), Medium (Filtering), and Heavy (AI/External API).
*   **Latency Estimates:** Documented p50/p95 latency targets (e.g., Browsing < 400ms, AI Advice ~5-8s).
*   **Concurrency Limits:** Established a realistic baseline of **~10-15 concurrent users** on KVM 1, limited primarily by the single vCPU and the 10-thread Apache cap for blocking AI calls.
*   **Growth Roadmap:** Defined "Tiers" for upgrading (e.g., Tier 2 = KVM 4 when subscribers > 200).

### 3. Repository Hygiene
*   Updated `.gitignore` to exclude `spike_log.txt` (the output of the diagnostic tool) to prevent log data from polluting the repository.
*   Consolidated temporary analysis files into the permanent documentation.

## Outcome
**Status:** SUCCESS

*   **Diagnostics:** The user successfully ran the automated scripts, confirmed MySQL was stopped, and captured the required logs for the host without manual timing stress.
*   **Documentation:** The project now has a clear architectural roadmap for scaling, moving away from reactive support tickets to proactive planning.
*   **Optimization:** Identified that applying `Nice=19` / `CPUSchedulingPolicy=idle` to the Celery worker is the "Single Best Change" to stabilize web performance on the current hardware.

## Future Recommendations
*   **Execute Optimization:** Apply the `Nice=19` change to the systemd service file on the live server.
*   **Monitor Ingestion:** Use `capture_spike.sh` periodically to verify if the Ingestor's CPU usage grows as the database size increases.
