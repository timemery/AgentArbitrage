# Dev Log Entry: The Recharge Wait, Confirmed Live

**STATUS BLOCK**
- **CLOSED: the 2026-09-19 entry's §7.5** — "the retry path has not been observed surviving a live dip." It has now, on the box, 2026-09-20.
- **One continuous run since 2026-09-19 17:08:31, no relaunch.** Launched on `595f3bb`.
- **369 recharges waited out and survived**, each followed by the same batch completing. The consecutive-wait counter resets as designed; the cap of 10 was never approached. Before #349, any one of those 369 would have ended the run.
- **Progress at 16:23:48Z:** attempted 1905 / 4000, repaired 1758, skipped 147. ~2,095 rows left.
- **Real sizing figure for a future sweep: ~82 rows/hour wall clock** — not "8-10 days at the 1000 xAI default", not "300-340/hour". §2.
- **No code or doc changes.** This records an observation; nothing was built or deployed.
- **Open and unchanged:** §7.1 the per-run attempted set, §7.2 Trello #144, §7.3 the uncommitted `max_xai_calls_per_day = 5000`.
- **STATUS: SWEEP STILL RUNNING.** Nothing here reports a finished sweep.

**Date:** September 20, 2026
**Files:** none — observation only
**Status:** OBSERVED — PR #349's fix works in production.

---

## 1. What Was Observed

**Reported by Tim from the live box. Not reproduced or verified in a sandbox** — the evidence below is the record.

PR #349 taught `repair_pricing.py` to sleep through a `TokenRechargeError` and retry the same batch. It shipped with 18 tests and zero live dips observed, which the previous entry flagged as the honest limit on the claim. That gap is now closed.

| check | output |
| :--- | :--- |
| `ps -o lstart= -p 3730095` | `Sat Sep 19 17:08:31 2026` |
| `grep -c "Keepa recharge needed" Diagnostics/repair_pricing.log` | `369` |
| progress at `16:23:48Z` | attempted 1905 / 4000, repaired 1758, skipped 147 |

One wait captured end to end:

```
14:55:09Z WARNING Keepa recharge needed (Recharge needed: 228s). Waiting 243s
(+15s margin), then retrying the same batch of 5.
```

followed by continued `WROTE` and `Batch of 5` lines — the same batch, written. The counter was seen reading `Recharge wait 1 of 10` mid-run, confirming it resets after each batch that gets through rather than accumulating.

---

## 2. The Real Sizing Figure

**~82 rows/hour**, over 23h15m of wall clock for 1905 rows. While actually working the sweep does **~320 rows/hour** — batches of 5 in ~56s. The gap is recharge waiting: 381 batches at ~56s is about **5.9 hours of work inside 23.25 hours of wall clock**, so roughly **three-quarters of the run is spent waiting** on the Keepa bucket it shares with ingestion, which Beat drives every 5 minutes (`celery_config.py:30-40`). At 82/hour the remaining ~2,095 rows are about **25 hours** of continuous running.

This supersedes both earlier estimates for planning: "8-10 calendar days" was xAI-bound at the 1000/day default, and "300-340 rows/hour" is the *working* rate, not the achieved one.

**Deliberately NOT written into `System_State.md` or `AGENTS.md`.** The box runs an uncommitted `max_xai_calls_per_day = 5000`; the committed docs describe the committed default of 1000, where xAI genuinely is the binding constraint, and are correct as written. Editing them to match a local override would make them wrong for anyone who pulls the repo.

---

## 3. Open Items

Carried forward unchanged from 2026-09-19.

1. **§7.1 — the per-run attempted set.** 147 skips so far. This run is unaffected (they are excluded for its duration), but a relaunch re-pays ~7 Keepa tokens per skipped row and sorts them back to the top. Owner decision.
2. **§7.2 — Trello #144**, the reasonableness check fails open on the error path.
3. **§7.3 — `max_xai_calls_per_day = 5000`** on the box, uncommitted, still to revert when the sweep ends.
4. **The sweep itself.** ~2,095 rows left, running.
