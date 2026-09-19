# Dev Log Entry: The Sweep Did Not Finish On Its Own

**STATUS BLOCK**
- **Shipped:** PR #349 — `repair_pricing.py` waits out a `TokenRechargeError` instead of ending the run. Sleep the requested seconds + 15s, log it, retry the same batch; consecutive waits capped at 10, then a clean exit 0. Every other exception still stops the run.
- **Live:** merged as `595f3bb`; box fast-forwarded `584e793 → 595f3bb` (also picking up #348's dev log). **Deployed by `git pull` alone — no `deploy_update.sh`**, and that was the correct call, not a shortcut. See §8.
- **What changed for you:** a run no longer dies on a 130-second token dip. Before #349, **every** recharge ended the sweep — 2026-09-17 stopped at 17:05:50 UTC after ~1 hour (339 repaired), and the 2026-09-18 relaunch on the old code died again.
- **The previous entry's "the sweep finishes on its own" was wrong.** It could not, by construction. That is §2.
- **Stale rows:** 4,634 → 4,295 (09-17 run) → 4,000 (09-18 run) → relaunched on the new code 2026-09-19 17:08 UTC at 4,000.
- **OPEN, and now the biggest thing in the way:** skipped rows sort back to the **top** of every new run. First 15 attempted on 09-19: **1 repaired, 14 skipped.** The attempted set is per-RUN, not per-table. Needs an owner decision — §7.1.
- **Also open:** `max_xai_calls_per_day` still 5000 on the box, uncommitted, still to revert. Trello #144 unchanged.
- **STATUS: FIX SHIPPED AND LIVE. SWEEP STILL IN PROGRESS.** Nothing here reports a finished sweep.

**Date:** September 19, 2026
**Files:** see §9
**Status:** SHIPPED — one PR merged (#349); the sweep it exists to keep alive is running.

---

## 1. Task Overview

Trello #139, continued. The sweep started on 2026-09-17 was supposed to run for days. It ran for about an hour.

```
ERROR Batch failed (Recharge needed: 130s). Stopping; nothing in this batch was written.
```

One PR: make `repair_pricing.py` wait the recharge out and retry the same batch, with a cap so it cannot spin, keeping every existing stop condition untouched.

Scope held to `repair_pricing.py`, its tests and `Documentation/System_State.md`. `token_manager.py` and ingestion were out of bounds and were not touched.

---

## 2. Premises That Turned Out Wrong

**(a) "The sweep finishes on its own."** — mine, in the 2026-09-17 status block and again in that entry's §7.1. **Wrong, and wrong in a way that was knowable when I wrote it.** The sweep could not finish on its own, because any `TokenRechargeError` ended it (`repair_pricing.py`, the blanket `except Exception` around `repair_batch`).

The evidence:

| run | launched | ended | result |
| :--- | :--- | :--- | :--- |
| 2026-09-17 | 16:08 UTC | **17:05:50 UTC** | 339 repaired, 31 skipped, 375 attempted, 4,295 stale left |
| 2026-09-18 | 19:35 UTC | before the next check | 4,295 → 4,000 stale |

The 09-17 arithmetic is worth reading closely: **375 attempted = 339 repaired + 31 skipped + the 5 rows of the batch the recharge killed.** The attempted set is updated *before* the fetch, so those 5 are in the count and were never written. That is the fix's whole surface area in one line.

**(b) "xAI is the binding constraint, so the sweep takes 8-10 days."** — mine, in the same entry, stated without qualification. **True only at the 1000/day default.** The box is running `max_xai_calls_per_day = 5000`, and at 5000 the pace is set by **Keepa** — 25/min, shared with ingestion — at roughly **300-340 rows an hour**. The 09-17 run's 339 rows in ~57 minutes is that figure. xAI stood at **90 of 5000 at launch** and was never a factor (the brief recorded 79 used; either way, two orders of magnitude from the cap).

The "8-10 calendar days" in `System_State.md` and `AGENTS.md` §7.13 is not wrong — it is stated against the 1000 default, which is what the repo ships. It is just not what is happening on the box right now. Flagged in §7.4 rather than edited, because the local 5000 is a temporary owner change and the committed figure should describe the committed default.

---

## 3. Hypotheses Raised and Discarded

**"Re-select the batch through `fetch_targets` after the wait."** The obvious implementation and a silent disaster. A batch's ASINs are added to the per-run attempted set **before** the fetch, and `build_target_sql` excludes `attempted_this_run` in SQL — so re-selecting after a recharge would filter out exactly the rows being retried and the batch would vanish with no error and no log line. The retry uses the target list already in memory. Pinned by `test_the_retry_is_not_re_selected_past_the_attempted_set`, whose `fetch_targets` stub honours the attempted set the way the real SQL does; without that stub the test would pass on broken code.

**"Read the wait off the exception object."** Not available. `TokenManager` embeds the figure only in the message string — `TokenRechargeError(f"Recharge needed: {wait_time}s")` at `token_manager.py:299` and `f"Insufficient tokens: wait {wait_time}s"` at `:440`. Parsing text is unlovely; the alternative was changing `token_manager.py`, which is shared with ingestion and out of scope. An unparsable message falls back to 60s and waits anyway, so a future reword cannot resurrect the stop.

**"Clamp a single wait to something tight, like 300s."** Discarded. Clamping returns to the retry before the tokens exist, so it burns a retry off the cap for nothing. `MAX_RECHARGE_WAIT_SECONDS = 1800` (`repair_pricing.py:241`) is a sanity clamp against a nonsense figure, not a tuning knob — real waits are bounded by `BURST_THRESHOLD` (50, +5 on the reservation path) over the refill rate, and the sweep already stops below 20/min, so the realistic maximum is ~165s.

**"One `time.sleep(145)`."** Discarded. `pkill -f repair_pricing.py` is the documented clean stop; a single long sleep makes the process look hung for the whole wait. Sliced into 5s (`RECHARGE_POLL_SECONDS`, `:246`), checking the stop flag between slices.

**"Leave the per-row `except Exception` in `repair_batch` alone — it's pre-existing."** Nearly did. Discarded on the second reading: `get_seller_info_for_single_deal` reserves tokens of its own (`seller_info.py:45`), so a recharge can surface inside the per-row loop, where the blanket handler records it as an **unrepairable row** — marking a perfectly good row failed *and* excluding it from every later batch that run. Pre-existing, yes; but waiting recharges out turns that from a once-per-run event into a **once-per-dip** one. Leaving it would have made the fix actively worse than the bug. It is re-raised now (`repair_pricing.py:737`).

---

## 4. Root Cause

**`TokenManager` raises instead of sleeping, deliberately, for a caller that does not exist here.**

When the calculated wait exceeds 60 seconds it raises rather than blocking (`token_manager.py:299`, `:440`). That is correct for the Smart Ingestor: it runs every 5 minutes under a Celery lock, so exiting releases the lock and frees the worker for the Janitor and gating checks, and Beat brings it back. `smart_ingestor.py:642` catches exactly that and returns.

`repair_pricing.py` inherited the contract and none of the preconditions. It holds **no lock**, has **nothing else to do**, and has **no scheduler to bring it back**. "Release and come back later" degenerates into "exit, and wait for a human to notice." Combined with `main`'s blanket `except Exception` treating the batch as fatal, a 130-second dip in a bucket the sweep *shares with ingestion by design* ended a multi-day run.

Neither component is wrong on its own. The interaction is — the same shape as #346's fail-open check meeting a "mark this as done" stamp.

---

## 5. The Fix

`TokenRechargeError` now sleeps the seconds the exception asks for plus `RECHARGE_WAIT_MARGIN_SECONDS = 15` (`:229`), logs the wait, and retries the same batch from the list already in memory. The margin exists because the wait `TokenManager` computes reaches `BURST_THRESHOLD` **exactly**; arriving with nothing to spare invites an immediate second recharge, and at 25/min 15s buys ~6 tokens of slack.

Four properties, each with a test:

- **The retry is not re-selected.** §3, first item.
- **Every existing stop condition still applies.** The wait returns to the **top** of the batch loop, so the xAI headroom guard, the 20/min refill floor and SIGTERM are all re-checked before each retry. Nothing was relaxed.
- **Consecutive waits are capped** — `--max-recharge-retries`, default 10 (`:255`) — and hitting the cap is **exit 0 and resumable**, like the xAI headroom stop, not a failure a wrapper should alarm on. The counter resets on the first batch that gets through (`:1082`), so it bounds a *stall*, not a long run: a sweep that dips once an hour never accumulates towards it.
- **A mid-batch recharge is re-raised, not filed as a skip.** §3, last item. Cost: rows already gathered in that batch are discarded unwritten and re-fetched on the retry — at most four, ~7 tokens each. That is the price of not losing them.

### Measured

**Before.** 2026-09-17, launched 16:08 UTC, dead 17:05:50 UTC on `Recharge needed: 130s` — 339 repaired in ~57 minutes, then nothing for 26 hours until a human relaunched it. 2026-09-18 19:35 UTC, relaunched on the same old code, stopped again before the next check (4,295 → 4,000 stale). Two runs, two recharge deaths, ~300 rows each.

**After.** Relaunched 2026-09-19 **17:08 UTC** on `595f3bb`, 4,000 stale at launch. It is running. **Honest limit on this claim:** what has been observed is the launch and the first 15 rows — 1 repaired, 14 skipped — which is the skip backlog of §7.1, not a recharge. The retry path itself is proven by 18 tests, all 18 of which fail on the parent commit; it has not yet been *observed* surviving a live dip. Suite 245 → **263**.

---

## 6. Deployment Result

`584e793 → 595f3bb`, a fast-forward that also brought in #348's dev log.

**Deployed with `git pull` and nothing else. No `deploy_update.sh`.** That is not a corner cut — running the deploy script would have been the wrong thing to do, for two reasons established this session by reading it:

1. **Nothing needed restarting.** No running service imports `repair_pricing.py` (§8), so a change confined to that file, its tests and a doc is live the moment the file lands on disk. The next `repair_pricing.py` invocation picks it up.
2. **`deploy_update.sh` would have broken the sweep.** It is not a restart script. It `chown -R www-data` the whole tree, runs `kill_everything_force.sh` (Redis `FLUSHALL`), `Diagnostics/force_clear_locks.py`, and `Diagnostics/force_pause.py` — which **forces Recharge Mode**, deliberately, to stop the system restarting on low tokens. Against a sweep whose only problem is low tokens, that is the worst available action.

---

## 7. Open Items

**7.1 — Skipped rows sort back to the top of EVERY new run. This is now the main brake.**
The attempted set is per-**run** (`attempted = set()` in `main`), which is right within a run: it stops an unrepairable row looping forever. Across runs it does nothing. A row skipped in run N keeps its stale `Pricing_Logic_Version`, so it matches the predicate again in run N+1 and — being priced, often visible — sorts straight back to the **top**. Measured on the 09-19 launch: **first 15 attempted, 1 repaired, 14 skipped.** Each relaunch re-pays ~7 Keepa tokens per known-unrepairable row before reaching any new work, and the backlog grows every run (31 after 09-17 alone). The 2026-09-17 entry flagged the *symptom* (§7.7, "rows with no used offer keep their old prices"); this is the scheduling consequence, and it compounds. **Owner decision needed** — the obvious candidates are a persisted skip list or a stamped "attempted and rejected" marker, both of which change what the predicate means. Not touched.

**7.2 — Trello #144, the reasonableness check fails open on the ERROR path.** Unchanged by this PR. `stable_calculations.py:127-130` catches `(HTTPStatusError, RequestError, Exception)` and returns `True`, so a transient xAI outage passes prices exactly as the daily cap used to. The headroom guard does not cover it and neither does this.

**7.3 — `max_xai_calls_per_day` is still 5000 on the box, uncommitted.** Still to revert when the sweep ends. A stale 5000 quietly raises the xAI bill on every future run. Same item as 2026-09-17 §6; repeated because it has not happened yet.

**7.4 — The "8-10 days" figure assumes the 1000/day default.** At the box's current 5000, Keepa sets the pace at ~300-340 rows/hour. The committed docs describe the committed default and were left alone; if 5000 ever becomes the default, `System_State.md` and `AGENTS.md` §7.13 both need the sizing rewritten against Keepa instead of xAI.

**7.5 — The retry path has not been observed surviving a live dip.** §5. It is tested, not witnessed. The next log line to look for is `Keepa recharge needed (...). Waiting 145s` in `Diagnostics/repair_pricing.log`, followed by the batch completing.

---

## 8. Infrastructure Findings

Facts established this session by reading source, written down nowhere else in the repo.

**No running service imports `repair_pricing.py`.** The Celery `imports` tuple at `celery_config.py:9-21` names eleven modules — `Keepa_Deals`, `tasks`, `smart_ingestor`, `recalculator`, `sp_api_tasks`, `env_diag`, `diag_task`, `janitor`, `maintenance_tasks`, `inventory_import`, `prime_picks_task` — and `repair_pricing` is not among them. `wsgi.py:5` imports only `wsgi_handler`. A repo-wide grep finds the only non-test references are two docstring mentions in `keepa_deals/pricing_version.py:55,77`. **Consequence: a change confined to `repair_pricing.py`, its tests and docs needs `git pull` and nothing else** — no restart, no `deploy_update.sh`, and it does not disturb a sweep in flight (the running process keeps the code it started with; the next invocation gets the new code).

**`deploy_update.sh` is not a restart script.** Read in full this session: it `sudo chown -R www-data:www-data` the entire application directory, runs `kill_everything_force.sh` (Redis `FLUSHALL` + `SAVE`), then `Diagnostics/force_clear_locks.py`, then `Diagnostics/force_pause.py` — which **forces Recharge Mode** to prevent a livelock on restart — then `start_celery.sh`, copies `agentarbitrage.conf` into `/etc/apache2/sites-available/`, `a2ensite`, restarts Apache and touches `wsgi.py`. Running it against a live `repair_pricing.py` sweep would kill nothing directly (the sweep is not a Celery task) but would flush the shared token bucket and force a recharge, which is precisely the condition the sweep was just taught to survive. Consistent with the 2026-09-17 finding that it does **not** run the schema migration.

**The Beat schedule, for the record** (`celery_config.py:30-40`): `smart-ingestor-run` on `crontab(minute='*/5')`, `janitor-clean-stale-deals` on `crontab(minute=0, hour='*/4')` with `grace_period_hours: 72`. Both compete with the sweep for the same Redis token bucket, which is why recharge dips are structural rather than incidental.

**`TokenRechargeError` carries its wait only in the message string,** not as an attribute — `token_manager.py:299` and `:440`. Any caller that wants to act on the figure must parse text, which is why `recharge_wait_seconds` (`repair_pricing.py:600`) exists and why it falls back rather than failing.

---

## 9. Files Modified

**PR #349 (merged, `595f3bb`) — wait out the recharge:**

| file | change |
| :--- | :--- |
| `repair_pricing.py` | recharge constants (`:229-255`), `recharge_wait_seconds` (`:600`), `sleep_through_recharge` (`:618`), mid-batch re-raise (`:737`), the retry loop and cap in `main` (`:981-1082`), `--max-recharge-retries`, docstring section "WAITING OUT A RECHARGE" |
| `tests/test_repair_pricing.py` | `ARechargeIsWaitedOutNotStopped`, 18 tests, all 18 failing on the parent commit |
| `Documentation/System_State.md` | stop conditions consolidated into one table under "Pricing Logic Version & Repair", plus why a recharge is not one of them |

**Suite:** 245 → 263.
