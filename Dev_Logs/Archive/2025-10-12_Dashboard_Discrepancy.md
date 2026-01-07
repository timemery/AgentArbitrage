# Dev Log: Dashboard Discrepancy Investigation & Diagnostic Consolidation

**Date:** October 12, 2025 **Task:** Investigate Data Discrepancy (Dashboard: 106 vs. Diagnostics: 210) & Consolidate Diagnostic Tools **Status:** Success

## 1. Task Overview

The user reported a significant discrepancy between the number of deals displayed on the web dashboard (106 deals) and the number reported by the backend diagnostic scripts (210 deals). The concern was potential data loss ("losing more data in the dashboard than we should").

The objective was to:

1. Determine if the missing 104 deals were actually lost or just hidden.
2. Update the diagnostic tools to accurately reflect what the user sees on the dashboard.
3. Consolidate multiple fragmented diagnostic scripts into a single, authoritative source of truth.

## 2. Investigation & Root Cause

**The Discrepancy:**

- **Raw Database Count:** 210 records.
- **Old Diagnostic Report:** 210 records (matched DB).
- **Dashboard Display:** 106 records.

**The Finding:** The discrepancy was **not data loss**. It was caused by a specific default filter applied by the dashboard's API endpoint (`/api/deals`) and the frontend.

- **The Filter:** `margin_gte=0` (Margin ≥ 0%).
- **The Effect:** The dashboard explicitly hides any deal where the `Margin` is negative or `NULL` (e.g., waiting for calculations).
- **Verification:** A test simulated the dashboard's API call (`/api/deal-count?margin_gte=0`) and returned exactly **106** deals. The remaining **104** deals existed in the database but had negative margins or missing data, correctly excluding them from the default "profitable" view.

## 3. Technical Implementation

To address the confusion and streamline future debugging, we consolidated the diagnostic suite.

### A. New Script: `Diagnostics/comprehensive_diag.py`

We replaced three separate scripts (`verify_api_counts.py`, `test_filtered_counts.py`, `count_stats.sh` logic) with a single Python script.

- Functionality:
  1. **Log Parsing:** Uses command-line text search tools (via `subprocess`) to count rejection reasons from `celery_worker.log` without loading the full file (safe for large logs).
  2. **Raw DB Count:** Queries `SELECT COUNT(*) FROM deals` to prove data persistence.
  3. **Dashboard Visible Count:** Queries `SELECT COUNT(*) FROM deals WHERE Margin >= 0` to match the UI's logic.
  4. **API Verification:** Simulates internal requests to `/api/deal-count` (both raw and filtered) to ensure the API matches the database.
- **Output:** Prints a unified report showing "Total Processed", "Successfully Saved", and crucially, **"Dashboard Visible"**.

### B. Updated Wrapper: `Diagnostics/count_stats.sh`

- Modified to act as a lightweight wrapper that executes `python3 Diagnostics/comprehensive_diag.py`.
- **Benefit:** Preserves the user's muscle memory (running `./Diagnostics/count_stats.sh`) while delivering the upgraded Python-based reporting.

### C. Cleanup

- Deleted `Diagnostics/verify_api_counts.py` (Obsolete).
- Deleted `Diagnostics/test_filtered_counts.py` (Obsolete).

## 4. Challenges & Learnings

- **Hidden Logic:** The primary challenge was realizing that the diagnostic scripts were "too raw"—they looked at the DB without context. The dashboard is a *view* of the data, not the raw data itself.
- **Diagnostic "User Experience":** Simply proving the data existed wasn't enough; the diagnostic tool needed to speak the user's language ("What will I see on the screen?"). Adding the "Dashboard Visible" metric bridged the gap between backend reality and frontend expectation.
- **Consolidation:** Moving from Bash to Python for the main logic allows for more complex checks (like simulating Flask API calls) which provides much stronger guarantees of system health than simple SQL counts.

## 5. Outcome

The task was **successful**.

- Confirmed zero data loss (210/210 records preserved).
- Explained the 106 count (104 items hidden by profit filters).
- Delivered a robust, single-command diagnostic tool that reports both numbers to prevent future confusion.
