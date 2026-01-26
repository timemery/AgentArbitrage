# Dev Log: Keepa Query Restoration & Diagnostics Update

**Date:** 2026-01-26
**Author:** Agent "Jules"
**Task:** Investigate "Dwindling Deals" & Restore Deal Volume

---

## 1. Overview
The user reported that the Backfiller appeared to stop running, with deal counts dropping significantly (from ~1000 to ~50). This was traced to a recent modification of the `keepa_query.json` file which overly restricted the Sales Rank range. Additionally, the user requested better visibility into whether the scheduled upserter (Celery Beat) was actually running.

## 2. The Issue
*   **Dwindling Deals:** The `keepa_query.json` configuration had been modified to restrict `salesRankRange` to `[50000, 1000000]`. While intended to improve quality, this combined with strict filters (Price > $20, Delta Drop > 20%) resulted in a massive drop in matching deals (only ~54 found).
*   **Diagnostic Blind Spot:** The existing diagnostic scripts (`diagnose_dwindling_deals.py` and `comprehensive_diag.py`) checked Redis locks and database timestamps but did not report whether the scheduler process (`celery beat`) was actually alive.

## 3. The Solution

### A. Keepa Query Restoration
We restored the `keepa_query.json` parameters to their "Original" values:
*   **Sales Rank Range:** Restored to `[100000, 5000000]` (was 50k-1M).
*   **Delta Range:** Restored to `[0, 10000]` (was missing).
*   **Result:** A test run confirming the deal count immediately increased to the page limit (150) from ~50.

### B. Diagnostic Enhancements
We updated both `Diagnostics/diagnose_dwindling_deals.py` and `Diagnostics/comprehensive_diag.py` to include a new check:
```python
# Checks if 'celery beat' process is running using pgrep
subprocess.run(['pgrep', '-f', 'celery beat'], ...)
```
This now explicitly reports: `[OK] Scheduled Upserter (Celery Beat) is RUNNING.` (or WARNING if not).

### C. Cleanup
Deleted the obsolete `Diagnostics/count_stats.sh` script, as `comprehensive_diag.py` now supersedes it.

---

## 4. Key Investigation Findings & Future Work

### Critical Data Mismatch (API vs UI)
During the investigation, the user noted that the Keepa Deals **Website** shows 20,000+ deals for certain parameters, while our API query returns **0** deals for the same high-rank range (1M-5M).
*   **Our Findings:** We ran targeted scripts (`Diagnostics/analyze_high_rank_quality.py`) querying the API for Ranks 1M-5M with loose filters (lowered price to $15, removed drop requirements). It consistently returned **0 results**.
*   **Conclusion:** There is a fundamental disconnect between what the Keepa UI shows and what the API returns for "Long Tail" books. This warrants a dedicated investigation task.

### The "Date Range" Standard
We reaffirmed a critical system standard regarding the `dateRange` parameter in `keepa_query.json`:
*   **Standard:** `dateRange: 3` (90 Days / Month window).
*   **Restricted:** `dateRange: 4` (All Combined).
*   **Reason:** Previous incidents showed that using `dateRange: 4` caused the API to return "Ancient Data" with timestamps from 2015, which clogged the ingestion pipeline and caused massive rejections. **Do not use dateRange: 4.**

---

## 5. Outcome
*   **Status:** SUCCESS
*   **Fix:** Deal volume restored.
*   **Tooling:** Diagnostics now report scheduler health.
*   **Reference:** This log serves as the baseline for the upcoming task to investigate the API vs UI data discrepancy.
