# Dev Log Entry: Fix Token Livelock Regression, Batch Deficit Lockout & Transition to Claude Code

**Date:** August 18, 2026
**File:** `Dev_Logs/2026-08-18_Fix_Token_Livelock_Regression_And_Batch_Deficit.md`
**Status:** SUCCESS — THREE ROOT CAUSES IDENTIFIED & FIXED LIVE, VERIFIED IN PRODUCTION, PUSHED TO MAIN

---

## 1. Task Overview

The Dashboard's newest deal had aged to ~9–11 hours (normally minutes), and deal ingestion had effectively stalled. This followed the same Keepa plan upgrade (5 → 25 tokens/min) that triggered the August 16 livelock, indicating the earlier fix had either regressed or was incomplete against a second, deeper failure mode.

The goals of this task were to:
1. Diagnose why the Smart Ingestor was aborting every 5-minute cycle without saving deals, despite the August 16 `BURST_THRESHOLD` fix.
2. Apply permanent, surgical fixes to restore continuous ingestion on the live 25 tokens/min plan.
3. Migrate the project's development documentation into the VM Knowledge Base vault so it is readable by Claude, and stand up Claude Code (web) as the replacement for Jules.

This session was performed hands-on against the live production server (`/var/www/agentarbitrage`) with Claude as technical advisor, reading real code and Redis/Keepa state before each edit. No agent (Jules or Claude Code) modified production code during this session; edits were applied directly and then committed to `main` from the VPS.

---

## 2. Challenges Faced & Deep Investigations

### A. BURST_THRESHOLD Regression to 280 (First Livelock)
* **Discovery:** Live diagnostics showed `Waiting for tokens to reach 280 (Burst Threshold)` while `Token_Management_Strategy.md` documents a cap of **50** for refill rates >= 20/min.
* **Mechanism:** `token_manager.py` line 37 hardcodes `self.BURST_THRESHOLD = 280` as an initial guess, intended to be overwritten by `_adjust_burst_threshold()`. That adjustment only runs on a successful Redis rate-load or a successful token sync. Because the worker was pinned in Recharge Mode and skipping syncs, the adjustment never fired, leaving the live threshold frozen at 280.
* **The Math:** Recovering from a deep deficit up to +280 at 25/min required ~17 minutes of pure waiting — far beyond the 60s `TokenRechargeError` abort limit — so the ingestor could never climb out and exited every cycle.

### B. Force-Sync Blocked by Its Own Throttle (Recovery Deadlock)
* **Discovery:** Logs repeatedly showed `Executing FORCE SYNC to verify state` immediately followed by `Skipping sync_tokens (throttled, force=True, elapsed=...s)`.
* **Mechanism:** In `sync_tokens`, the throttle used `throttle_limit = 60 if not force else 300`. A forced sync in Recharge Mode — the exact call meant to rescue the worker by fetching Keepa's true balance — was still subject to a 300s throttle. It therefore acted on a stale, over-counted local balance and aborted.
* **The Consequence:** A chicken-and-egg deadlock — the worker could not sync because it was starved, and stayed starved because it would not sync. Redis token state drifted well below Keepa's real balance (observed: Redis -229 vs Keepa -104).

### C. 50-ASIN Peek Batch Deficit Sledgehammer (Second Livelock — the true root cause)
* **Discovery:** After fixes A and B, the ingestor successfully exited Recharge Mode, fetched 300 deals, then a single log line read: `Lightweight batch call successful. Tokens consumed: 386. Tokens left: -231`.
* **Mechanism:** `smart_ingestor.py`'s dynamic batch-sizing (`SCAN_BATCH_SIZE`) reduced the peek batch only for slow plans (1 ASIN below 10/min, 20 ASINs below 20/min). At 25/min the code fell through to the default **50-ASIN** batch. A 50-ASIN peek at `days=365, offers=20` costs ~386 tokens — larger than the entire refillable budget on a 25/min plan. The cost pre-check reserved only `2 * len(chunk)` (~100 tokens), a ~4x underestimate, so the deficit guard never triggered.
* **The Consequence:** The first analysis batch of every cycle instantly drove the balance from positive to ~-231, forcing ~5 cycles of recharge before it could try again — and then repeat. This is why fixes A and B alone were insufficient: they let the ingestor start, but the oversized batch immediately re-crashed it.

---

## 3. Solutions Implemented

### 1. BURST_THRESHOLD Default Lowered to 50 (`keepa_deals/token_manager.py`)
* **Action:** Changed the line-37 initial value from `self.BURST_THRESHOLD = 280` to `self.BURST_THRESHOLD = 50`.
* **Benefit:** Even if dynamic adaptation never fires (no Redis rate, no successful sync), the floor is the documented livelock-proof value. The recovery wait now stays within the 60s abort limit.

### 2. Force-Sync Now Bypasses the Throttle (`keepa_deals/token_manager.py`)
* **Action:** Changed the throttle guard from `if last_sync > 0 and (now - last_sync) < throttle_limit:` to `if (not force) and last_sync > 0 and (now - last_sync) < throttle_limit:`.
* **Benefit:** A forced sync in Recharge Mode always hits Keepa's `/token` endpoint, retrieves the authoritative balance, reconciles Redis via the existing `_sync_tokens_from_response` path, and re-adjusts the burst threshold. Routine (non-forced) syncs remain throttled to prevent token drain.

### 3. Mid-Tier Peek Batch Cap (`keepa_deals/smart_ingestor.py`)
* **Action:** Added a batch-sizing tier for refill rates >= 20 and < 30/min that caps `current_batch_size = 15` (~115 tokens per peek), sitting between the existing `< 20` (20 ASINs) and default (50 ASINs) branches.
* **Benefit:** One peek call now fits inside a refillable budget on a 25/min plan and recharges in ~5 minutes. Verified live: a 15-ASIN peek consumed **90 tokens** (down from 386), the balance dipped only to -8 (not -231), waited 44s, recovered to +42, and continued processing and committing deals.

---

## 4. Knowledge Base & Tooling Migration (Jules -> Claude Code)

* **Vault sync:** Ran `master-sync.sh --apply` to push the full `VisibleMedia/` markdown tree (including `AgentArbitrage/`) into the VM Knowledge Base vault. Confirmed 466 Mac markdown files landed (472 indexed after reindex; one unrelated Faceless note skipped for a YAML parse error). AgentArbitrage documentation is now readable by Claude in-chat.
* **Claude Code (web) stood up:** Connected via claude.ai Code on Opus 5 at maximum effort, cloning `timemery/AgentArbitrage` from GitHub. Onboarding using the adapted start-session template succeeded — the agent read all documentation in AGENTS.md order, respected the never-read list, and correctly flagged three environment facts (no `.env`, no `deals.db`, and a stale filename in AGENTS.md §4 item 9: `Feature_Guided_Learning_Strategies_Brain.md` should read `..._Intelligence.md`).
* **Open item — GitHub write access:** Claude Code committed a `session_backup.sh` script locally but could not push (403). The Claude GitHub App is authorized (read/OAuth) but not installed with write access to the repo; it does not yet appear under GitHub's "Installed GitHub Apps." This must be resolved before Claude Code can deliver work back, and before the Jules subscription is cancelled.

---

## 5. Verification & Success Status

**Status: SUCCESS**

1. **Fix A verified:** After deploy, the recharge target math changed from ~444s (toward 280) to values consistent with a target of 50, confirming the new default took effect.
2. **Fix B verified:** A forced sync in Recharge Mode executed against Keepa (no "Skipping ... force=True" line), retrieved the real balance (+140), and the worker logged `Burst/Buffer threshold reached (140.00). Exiting Recharge Mode` — then fetched 300 deals.
3. **Fix C verified:** Live log showed `Mid Refill Rate (25.0/min). Reducing SCAN_BATCH_SIZE to 15` followed by `Tokens consumed: 90. Tokens left: -8`, a graceful 44s wait, recovery to +42, and a successful commit batch (`Batch API call successful. Tokens left: 12`). The deficit sledgehammer is eliminated.
4. **Post-fix health:** Keepa balance positive and holding (+62). Diagnostic integrity checks pass (DB raw 2,378 matches API metadata; filtered 610 matches Dashboard API). Newest-deal age will trend down over subsequent cycles as the ~1,700-deal backlog clears at ~15 ASINs/cycle.
5. **Persisted to source:** Both files committed and pushed to `main` (`928135b`, following hotfix `0389ba8`), so the fixes survive future deploys.

---

## 6. Files Modified

- `keepa_deals/token_manager.py`: BURST_THRESHOLD default 280 -> 50; force-sync bypasses the throttle when `force=True`.
- `keepa_deals/smart_ingestor.py`: Added a 15-ASIN `SCAN_BATCH_SIZE` tier for 20–30/min refill plans.

## 7. Follow-Ups / Open Items

- Resolve Claude Code GitHub App write access (repo not yet in the installed set); then cancel the Jules subscription.
- Consider whether the newest-deal backlog should be cleared faster (temporary batch bump) once tokens are stably positive.
- Remove the `.bak-*` files created on the VPS during this session (`token_manager.py.bak-*`, `smart_ingestor.py.bak-*`).
- One-word doc fix in `AGENTS.md` §4 item 9: `Feature_Guided_Learning_Strategies_Brain.md` -> `..._Intelligence.md`.
- Future: mirror/staging server so development can be tested without touching the live site (user has a buried plan doc on this).
