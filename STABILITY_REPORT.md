# System Stability & Unresponsiveness Analysis

**Date:** December 2025
**Author:** Jules

## Executive Summary

The recurring unresponsiveness is primarily caused by **Resource Exhaustion** and **Context Window Overload**, triggered by massive log files (specifically `celery.log`) and an increasingly cluttered root directory.

It is **not** an issue with your computer's speed or memory. The issue lies in the volume of text the agent attempts to process, which exceeds the strict limits of the underlying LLM environment.

---

## Addressing Your Specific Question: "Are my warnings sufficient?"

**You asked:** *Is the text in my task description and `AGENTS.md` sufficient?*

**The Verdict:**
Your instructions are **linguistically perfect** (specific, actionable, prominent). However, relying on them is a strategy of **Hazard Avoidance** (warning signs), which fails when an agent inevitably prioritizes "gathering context" over "safety protocols."

**Recommendation:**
Switch to **Hazard Removal** (eliminating the file's size).

**You asked:** *Can I keep the head and tail of the log instead of deleting it?*

**Yes.** This is the best of both worlds: it preserves the startup context (head) and the most recent errors (tail) while removing the massive bulk of repetitive data in the middle.

---

## Remediation Plan (The "Stability Pact" Update)

To work together without interruptions, we must implement a strict hygiene protocol.

### Step 1: Log Pruning (Hazard Removal)
**Action:** Run this command **before** assigning the task. It will reduce the 115MB file to a few kilobytes, keeping only the first 50 and last 50 lines.

**The "Pruning" Command:**
```bash
(head -n 50 /var/www/agentarbitrage/celery.log && echo -e "\n... (LOG TRUNCATED BY USER FOR STABILITY) ...\n" && tail -n 50 /var/www/agentarbitrage/celery.log) > /var/www/agentarbitrage/celery.log.tmp && mv /var/www/agentarbitrage/celery.log.tmp /var/www/agentarbitrage/celery.log
```

*   **What this does:**
    1.  Reads the first 50 lines (`head`).
    2.  Inserts a warning marker ("... LOG TRUNCATED ...").
    3.  Reads the last 50 lines (`tail`).
    4.  Saves this "digest" to a temporary file.
    5.  Overwrites the original giant log with this lightweight digest.

*   **Agent Instruction Update:** Change your instruction to: *"I have pruned `celery.log`. It contains the startup logs and the most recent errors. It is safe to read."*

### Step 2: Codebase Cleanup (Context Management)
We should organize the repository to reduce cognitive load (noise) for the agent.

**Assessment of Specific Files:**

*   **`test_launch.log`**: **DELETE**. This is a stale artifact from a previous debugging session. It contains no code, only old output. It is safe to remove.
*   **`test_run.py`**: **ARCHIVE (or Move to `diagnostics/`)**. This is a manual trigger script. It is useful for testing but contributes to root directory clutter. It should be moved to the `diagnostics/` folder alongside other `diag_*.py` scripts.
*   **`tests/verify_dashboard.py`**: **ARCHIVE**. This is a specific Playwright verification script for the "Gated Column" feature. Since that feature is currently disabled/under maintenance, this test is not part of the active suite. Keep it for reference in `Documents_Dev_Logs/archive/` or a `tests/archive/` folder, but it is not needed for daily operations.

**Proposed Cleanup Actions (I can perform these if requested):**
1.  **Move Diagnostic Scripts:** Create a `diagnostics/` folder and move all `diag_*.py` (and `test_run.py`) files there.
2.  **Archive Dev Logs:** Create `Documents_Dev_Logs/archive/` and move older logs there.
3.  **Delete Artifacts:** Remove `test_launch.log` and `verify_dashboard.py` (or move to archive).

### Step 3: Focused Tasking
Your current approach of "single focused issue" is correct. To further improve stability:

*   **Explicit "Do Not Read":** In your prompt, list files the agent should *ignore* (e.g., "Do not read the full logs").
*   **Fresh Starts:** Continue requesting a "Fresh Sandbox" for every new task. This clears out temporary artifacts and ensures a clean slate.

## Conclusion

The "unresponsiveness" is a defense mechanism of the system protecting itself from data overload. By systematically "pruning" the log file before the agent sees it, you eliminate the possibility of a crash while preserving the critical information needed for debugging.
