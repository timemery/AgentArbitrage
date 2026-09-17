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
*   **`tests/verify_dashboard.py`**: **ARCHIVE**. This is a specific Playwright verification script for the "Gated Column" feature. Since that feature is currently disabled/under maintenance, this test is not part of the active suite. Keep it for reference in `Documents_Dev_Logs/archive/` or a `tests/archive/` folder, but it is not needed for daily operations.
*   **Trigger Scripts (`trigger_diag_task.py`, `trigger_env_diag.py`, `test_run.py`)**: **MOVE TO `diagnostics/`**.
    *   **Reasoning:** While these scripts are simple wrappers around `celery.send_task` and *could* be recreated, they contain the specific task names (e.g., `keepa_deals.env_diag.run_environment_diagnostic`) which are tedious to remember.
    *   **Recommendation:** Do not delete them. Moving them to a `diagnostics/` folder clears the root directory clutter while preserving these useful "shortcuts" for future debugging.
*   **Kill Scripts (`kill_everything.sh`, `force_kill.sh`)**: **DELETE**.
    *   **Reasoning:** You correctly identified that `kill_everything_force.sh` is the superior, most up-to-date version. A comparison confirms that `kill_everything.sh` is older, less robust (misses the "monitor" process), and redundant. `force_kill.sh` is also redundant as `kill_everything_force.sh` includes the same logic.
    *   **Recommendation:** Delete `kill_everything.sh` and `force_kill.sh`. Keep only `kill_everything_force.sh`.

### Step 3: Prompt Tuning (Final Verification)

**You asked:** *Is reading the last TWO Dev Logs (`dev-log-8.md` and `dev-log-9.md`) safe?*

**The Verdict: YES.**
*   **`dev-log-8.md`**: ~56 KB
*   **`dev-log-9.md`**: ~30 KB
*   **Total:** ~86 KB.

This is well within the safety margin. The danger arises when the agent attempts to read the *entire* `Documents_Dev_Logs/` folder, which contains huge files like `RAW_PRODUCT_DATA.md` (424 KB).

**Your Updated Prompt:**
Your revised prompt (filtering out `RAW_PRODUCT_DATA.md` and `Archive/` directories) is **excellent**. It is precise, restrictive where it needs to be, and permissive where it helps context.

**Stability Status:**
With **Log Pruning** (Step 1) and your **Revised Prompt** (Step 3), the risk of "unresponsiveness" due to context overload is effectively eliminated. You are ready to resume development.
