# System Stability & Unresponsiveness Analysis

**Date:** December 2025
**Author:** Jules

## Executive Summary

The recurring unresponsiveness is primarily caused by **Resource Exhaustion** and **Context Window Overload**, triggered by massive log files (specifically `celery.log`) and an increasingly cluttered root directory.

It is **not** an issue with your computer's speed or memory. The issue lies in the volume of text the agent attempts to process, which exceeds the strict limits of the underlying LLM environment.

---

## Addressing Your Specific Question: "Are my warnings sufficient?"

**You asked:** *Is the text in my task description and `AGENTS.md` (warning about the 115MB file and instructing to use `tail`) sufficient, or does it need to be more strongly worded?*

**The Verdict:**
Your instructions are **linguistically perfect**. They are:
1.  **Specific:** You mention the exact filename (`celery.log`) and size.
2.  **Actionable:** You provide the exact commands to use instead (`tail`, `grep`).
3.  **Prominent:** They are in the task description and `AGENTS.md`.

**Why is it still failing?**
If the text is perfect, why does the agent still become unresponsive?
1.  **Agent Fallibility:** In complex reasoning tasks, agents prioritize "gathering context." Sometimes, the urge to "read the log to find the error" overrides the instruction to "not read the *whole* file." The agent might intend to read "just a bit" but mistakenly uses a tool that fetches the whole thing.
2.  **Tooling Limits:** Some agent tools might try to index or "peek" at files automatically. A 115MB file acts like a black hole—even touching it can cause a timeout before the agent even decides to stop.
3.  **Hazard Avoidance vs. Hazard Removal:** Your current strategy is "Hazard Avoidance" (putting a "Do Not Touch" sign on a dangerous button). This relies on the agent reading the sign and obeying it every single time. A safer strategy is "Hazard Removal" (removing the button entirely).

**Recommendation:**
**Do not rewrite the warning. Remove the file.**
The most robust solution is to eliminate the possibility of error.

---

## Remediation Plan (The "Stability Pact" Update)

To work together without interruptions, we must implement a strict hygiene protocol.

### Step 1: Log Management (Hazard Removal)
**Action:** Truncate or delete the `celery.log` **before** assigning the task to the agent.

*   **Command:** `> celery.log` (This empties the file without deleting it, keeping the file handle valid).
*   **Why:** If the file is 0KB, the agent can mistakenly read the whole thing without crashing. You eliminate the risk entirely.
*   **Agent Instruction Update:** Change your instruction to: *"I have truncated celery.log. It is safe to read. If it fills up again, use `tail`."*

### Step 2: Codebase Cleanup (Context Management)
We should organize the repository to reduce cognitive load (noise) for the agent.

**Proposed Actions (I can perform these if requested):**
1.  **Move Diagnostic Scripts:** Create a `diagnostics/` folder and move all `diag_*.py` files there.
2.  **Archive Dev Logs:** Create `Documents_Dev_Logs/archive/` and move older logs (e.g., `dev-log-1` through `dev-log-6`) there.
3.  **Rotate Logs:** Consider adding a simple script or cron job to rotate `celery.log` automatically.

### Step 3: Focused Tasking
Your current approach of "single focused issue" is correct. To further improve stability:

*   **Explicit "Do Not Read":** In your prompt, list files the agent should *ignore* (e.g., "Do not read the full logs").
*   **Fresh Starts:** Continue requesting a "Fresh Sandbox" for every new task. This clears out temporary artifacts and ensures a clean slate.

## Conclusion

The "unresponsiveness" is a defense mechanism of the system protecting itself from data overload. By shifting from "warning about the file" to "managing the file's size," we can guarantee a stable environment for Jules.
