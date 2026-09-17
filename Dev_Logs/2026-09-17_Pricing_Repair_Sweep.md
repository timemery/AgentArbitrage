# Dev Log Entry: The Pricing Repair Sweep, and the Two Things the Dry Run Caught

**STATUS BLOCK**
- **Shipped:** PR #345 — `Pricing_Logic_Version` + `repair_pricing.py`, plus two review fixes (deal-feed carry-forward, per-run attempted set) and a guard refusing an unbounded dry run. PR #346 — the sweep stops before the xAI daily cap. PR #347 — the Keepa API key redacted from every error log.
- **Live:** box `ddd8c15 → fce3745` (#344, #345), then `→ 584e793` (#346, #347). Both deploys clean; the second at **16:02 UTC**.
- **STATUS: IN PROGRESS, NOT SUCCESS.** The full sweep started **16:08 UTC** (nohup, PID 3695242) and is **still running**. First batches repaired 4/5 and 5/5. It is expected to take 8–10 days. Nothing here reports a finished sweep.
- **The dry run is what earned its keep.** 10 rows, 15:05 UTC: 9 previewed, 1 skipped — and it surfaced **both** blockers. Neither was visible from the code alone.
- **Blocker 1 (#346):** past the xAI daily cap the reasonableness check returns `True` rather than failing (`stable_calculations.py:76`), so an inflated price would be accepted unchecked **and** stamped version 2 — dropping it out of the predicate forever. ~1.7 xAI calls per row means the cap arrives at ~500–600 rows.
- **Blocker 2 (#347):** a `seller=Unknown` 400 on 3 of 10 rows logged the **full Keepa API key**. `requests` puts the URL in its exception text and every fetcher logged `{e}` raw.
- **Live `--apply --limit 20`, 16:02 UTC:** 19 repaired, 1 skipped. `1890919489` **$1,000.00 → $124.85**; `0349104549` **$1,250.99 → $37.49**; `3037666471` **$1,214.00 → $451.65**. **12 of 19 went to NULL** — xAI rejected the price. All 19 carry version 2 and kept their `Deal_found`.
- **Next:** the sweep finishes on its own. Trello **#144** (check fails open), **#145** (key rotation), **#146** (`backup_db.sh` WAL), **#143** (xAI counter). Post-sweep checklist is on **#139**.

**Date:** September 17, 2026
**Files:** see §9
**Status:** IN PROGRESS — three PRs merged (#345, #346, #347); the sweep they exist to run is still executing.

---

## 1. Task Overview

Trello #139: repair the rows still carrying prices written before the 2026-09-12 price-association fix. The plan was approved the previous day — option (a), full scope, with a version column — and this entry covers building it, two rounds of review fixes, and the first live runs.

Three PRs, in the order the work forced:

| PR | what |
| :--- | :--- |
| #345 | `Pricing_Logic_Version` + `repair_pricing.py` |
| #346 | stop before the xAI daily cap |
| #347 | redact the Keepa API key from error logs |

**#346 and #347 were not planned.** Both came out of a single 10-row dry run, and neither was findable by reading the code — one needed the xAI counter to be observed under real load, the other needed a real 400 from Keepa. That is the entry's main lesson, recorded in §2.

Scope held: option (e) routing, the `backup_db.sh` WAL defect, the 240-hour window, the IQR at `n <= 3`, `clear_analysis_cache` and the xAI counter raciness (#143) were all out of bounds and none were touched.

---

## 2. Premises That Turned Out Wrong

**(a) "A dry run is a formality — the tests already prove the mechanics."** — mine, implicitly, in how I sequenced the work. **Wrong, and expensively so if it had held.** 225 tests passed on a sweep that would have silently laundered inflated prices after ~500 rows and published the API key on every seller 400. Both defects are invisible to a test suite because both need *production state that does not exist in a fixture*: a shared daily counter under real load, and a real Keepa error response.

Worth stating plainly because the temptation was real: the suite was green, the plan was approved, and the full sweep was one command away.

**(b) "The token reservation gates throughput, so the sweep is Keepa-bound."** — mine, in the planning report the day before. **Wrong, twice over.**

First, the reservation is transient: `request_permission_for_call` does `incrbyfloat(TOKENS, -cost)` (`token_manager.py:324`) and `update_after_call` then overwrites the bucket with Keepa's authoritative `tokensLeft` (`:545`). So throughput follows real consumption (~7/ASIN), not the blind 20. That correction went into #345 and roughly halved the Keepa estimate — 4,534 rows in ~42 hours rather than ~72.

Second, and more importantly, **Keepa was never the binding constraint at all.** The sweep makes ~1.7 xAI reasonableness calls per row, against a daily cap of 1000 shared with ingestion. That is ~500–600 rows a day — so the real figure is **8–10 calendar days**, set by a resource my planning report did not model.

**(c) "The heavy path on an existing row reproduces what the ingestor would write."** — mine, in #345's design. **Wrong for two columns**, caught in review.

The ingestor does `product_data.update(deal)` (`smart_ingestor.py:573`) before `_process_single_deal`, merging the /deal feed object into the product dict. `repair_pricing.py` has only the /product response, which cannot be fetched with a deal object for an arbitrary ASIN. So:

| column | deal-only key | repair wrote |
| :--- | :--- | :--- |
| `Deal_found` | `creationDate` — `stable_deals.py:88` | `'-'` |
| `last_price_change` | `currentSince` — `stable_deals.py:252` | `'-'` (the dashboard's **Ago**) |

Audited all 67 non-`None` `FUNCTION_LIST` entries plus every direct read in `_process_single_deal`, by source and then **empirically** — the whole list run twice against one fixture, with and without `creationDate`, `currentSince`, `current`, `lastUpdate`, `deltaPercent`. Exactly those two differ. `last update` is unaffected (`FUNCTION_LIST[10]` is `None`).

`last_price_change` is the more interesting of the two: it is called as `func(product_data)` with **one positional argument**, so the merged dict binds to its `deal_object` parameter and its own `product_data` parameter stays `None`. Its `csv` branch reads that parameter, so **that branch never fires on the ingestor either** — exactly the mechanism AGENTS.md §7.3 already describes for `last_update`. It always falls back to `currentSince`.

**(d) "Leaving an unrepairable row untouched is harmless."** — mine, in #345. **Wrong: it loops.** A row Keepa does not return, or that heavy processing rejects, stays stale and sorts straight back to the **top** of the next batch. An unlimited `--apply` run would re-fetch it forever at ~7 tokens a time; a dry run with `--limit 20` previewed the same 5 rows four times. Fixed with a per-run attempted set in a TEMP table.

---

## 3. Hypotheses Raised and Discarded

**"Use `_merge_db_keyed` for the carry-forward."** The obvious reach, and wrong. It applies the no-data guard to **every** column it merges, which is correct for the light path and exactly backwards here — it would preserve the stale `List_at` the sweep exists to replace, making the script an expensive no-op. Replaced by an explicit two-column allowlist; `_is_no_data` is reused for the sentinel test, which is the shared definition of "no value" and a different function.

**"Bound parameters for the attempted set."** Discarded for a TEMP table. If Keepa is unreachable the set reaches every row in the table, and `NOT IN (?,?,...)` has a variable-count ceiling. Temp tables work against a read-only main database and have none.

**"Warn on an unbounded dry run."** That was the original #345 behaviour and it was not enough. Once the attempted set fixed the loop, the dry run began walking the whole table — ~32,000 Keepa tokens for zero writes. A warning the operator can miss is not a guard; it is now refused with exit 1 **before preflight**.

**"Widen the carry-forward allowlist to anything that looks preserved."** Explicitly refused and written into `AGENTS.md` §7.13. Every pricing column must be overwritten, including to NULL.

---

## 4. Root Cause

Two separate root causes, both structural rather than accidental.

**For #139 itself: `List_at` and `1yr_Avg` have exactly one producer, and nothing can reach it.** They are computed only in `_process_single_deal`. The light path never recomputes them (`processing.py:405` has no `infer_sale_events` call); the Stale Rescue routes to that same light path and refreshes `last_seen_utc` every pass, so a row it keeps reaching is never reaped *and* never re-priced; `recalculator.py` is API-free and reads the stored value. And the heavy path is unreachable for an existing row because `smart_ingestor.py:577` routes purely on `asin in existing_asins_set`. A row written under old pricing logic is therefore immortal and permanently wrong. `repair_pricing.py` exists to be the one thing that forces the heavy path onto an existing ASIN.

**For #346: the reasonableness check fails OPEN.** When the daily cap denies permission, `_query_xai_for_reasonableness` does not raise and does not skip the row — it returns `True` (`stable_calculations.py:76-78`, *"Defaulting to reasonable"*). In normal ingestion that is a tolerable degradation. Inside this sweep it is catastrophic, because the sweep **also stamps `Pricing_Logic_Version = 2`** on the way past. An unchecked price is thereby marked current and drops out of the predicate, so the sweep never revisits it. The failure is silent, permanent, and leaves nothing in the data to show it happened.

That interaction — a fail-open check meeting a "mark this as done" stamp — is the part neither component is wrong about on its own.

**For #347: every Keepa URL carries the key, and `requests` puts the URL in the exception.** All five URL builders in `keepa_api.py` embed `key=<API key>` as a query parameter, and all ten error paths interpolated `{e}` or `{str(e)}` straight into a `logger.error`. So *any* Keepa HTTP error published the key into `celery_worker.log`.

---

## 5. The Fix

### PR #345 — the version column and the sweep

`Pricing_Logic_Version` (INTEGER), `PRICING_LOGIC_VERSION = 2` in `keepa_deals/pricing_version.py`, written **only** in `_process_single_deal` beside `Inferred Sale Count`. The NULL rule — *NULL or lower means stale, re-fetch it* — is deliberately the **opposite** of the `Inferred_Sale_Count` NULL rule, and the docs say so in three places, because the two look mergeable and are not: one decides whether a deal may be **shown**, the other whether work should be **scheduled**, and the cost of being wrong is asymmetric.

`repair_pricing.py` selects `version IS NULL OR < PRICING_LOGIC_VERSION`, repairs visible rows first, then priced by `List_at` DESC, then unpriced. Resumption needs no checkpoint: a repaired row carries the current version and stops matching.

**Two review fixes** (`6fee8dc`): the deal-feed carry-forward allowlist of §2(c), and the per-run attempted set of §2(d), with skipped ASINs written to their own manifest with reasons. **One more guard** (`739f048`): an unbounded dry run refused with exit 1 before preflight.

### PR #346 — stop before the cap

Before each batch, check the **same in-process `XaiTokenManager`** the reasonableness check uses. Stop with **exit 0** — a resumable pause, not a failure — when spare calls fall below `--xai-headroom` (default 50).

Two things found while wiring it, both handled rather than assumed:

- **The in-process count under-reports.** The manager reads its state file once at construction, then increments in memory, while ingestion writes the same file from two other instances. Under-reporting makes the guard fire **late**, which is the dangerous direction, so the on-disk count is folded in as a floor.
- **The state path is relative.** `state_path='xai_token_state.json'` resolves against the process's CWD. Run from anywhere but the application root, the guard reads a nonexistent file, counts zero and never fires — the exact silent failure it exists to prevent. Preflight now refuses to run outside the application root.

### PR #347 — redact the key

A `redact()` helper applied to **all ten** error logs, not just the seller fetcher that happened to be caught. By **pattern** rather than by comparing against the configured key, so a stale key or a second account's key is covered; applied to the **exception text**, because that is how the leak arrives; and it keeps the status code, ASIN list and rest of the URL, so a 429 stays debuggable.

### Measured, live

**Dry run, `--limit 10`, 15:05 UTC.** 9 previewed, 1 skipped (`0851514014`, no used offer). ~15 xAI calls for 9 rows. xAI state 78/1000.

**Live `--apply --limit 20`, 16:02 UTC.** Backup `deals.db.pricing-repair-20260917160251.bak`, 4,665 rows, verified. **19 repaired, 1 skipped.** Stale rows **4,653 → 4,634**.

| ASIN | stored | repaired |
| :--- | ---: | ---: |
| `1890919489` | $1,000.00 | **$124.85** |
| `0349104549` | $1,250.99 | **$37.49** |
| `3037666471` | $1,214.00 | **$451.65** |

**12 of the 19 went to `List_at` NULL** — the AI Reasonableness Check rejected the recomputed price outright. That is the sweep working as designed, and it is also why the visible deal count will fall.

All 19 carry `Pricing_Logic_Version = 2` and a **kept `Deal_found`**, confirming §2(c)'s fix end to end. 10 show `last_price_change` as `'-'` — checked against the backup, which shows `'-'` for the same rows. **Nothing was lost; those rows never had the value.**

---

## 6. Deployment Result

`ddd8c15 → fce3745` (#344, #345), then `→ 584e793` (#346, #347). Both `deploy_update.sh` runs clean, the second at 16:02 UTC.

**The new column did not appear at deploy time, and that is expected.** `create_deals_table_if_not_exists` runs in two places only: `wsgi_handler.py:2961` (`@app.before_request`, guarded by a `_db_initialized` flag set at `:2959`) and `smart_ingestor.py:311` at the start of an ingestion cycle. `deploy_update.sh` restarts services but does not itself touch the schema, so `Pricing_Logic_Version` was absent until the **first web request** after the restart. Worth recording: between deploy and that first request, `repair_pricing.py` would have failed on a missing column, and the cause would have looked like a broken migration rather than a not-yet-run one.

**The full sweep started at 16:08 UTC**, detached under `nohup`, PID 3695242. First batches repaired 4/5 and 5/5. **It is still running.** The xAI cap — not Keepa tokens — sets the pace, so expect 8–10 days of one run per day.

**One local change on the box, uncommitted and deliberate:** `settings.json` `max_xai_calls_per_day` raised from 1000 to **5000** for the duration of the sweep, by owner decision. **To be reverted when the sweep finishes.** It is not in the repo and will not survive a `git checkout` of that file — noted here because a stale 5000 would quietly raise the xAI bill for every future run.

---

## 7. Open Items

1. **The sweep itself.** Still running. The post-sweep checklist — verify the price distribution, refresh Prime Picks, revert `max_xai_calls_per_day` — lives on **Trello #139**.
2. **Trello #144 — the reasonableness check fails open on BOTH paths.** #346 guards the *cap*. The **error** path (`stable_calculations.py:127-130`) catches `(HTTPStatusError, RequestError, Exception)` and also returns `True`, so a transient xAI outage passes prices exactly as the cap did. The headroom guard does not cover it. The honest fix is for the pricing stage to treat "could not check" as "do not stamp as current" — a behaviour change beyond #346's scope.
3. **Trello #145 — the key leak, beyond `keepa_api.py`.** #347 stops it going forward but **cannot unpublish what is already written**. Rotation, an audit of other leak paths, and the `seller=Unknown` root cause all sit here.
4. **`seller=Unknown` (part of #145).** `get_used_product_info` returns the literal string `"Unknown"` when no live offer matches `stats.current[2]` (`seller_info.py:191`). It is truthy, so the `if not seller_id` guard passes it to Keepa → 400. **Normal ingestion does exactly the same** (`smart_ingestor.py:583` calls the same helper) — a pre-existing bug, not one the sweep introduced; the sweep just hits it more often because re-fetched rows are older and their offers have churned. The 400 costs ~no tokens, but `seller_info.py:49` calls `update_after_call(tokens_left)` unguarded and `float(None)` would raise if Keepa ever returned a non-JSON error body. The ingestor guards its own calls with `if tokens_left:`; this one does not.
5. **Trello #146 — `backup_db.sh` is a plain `cp` of a WAL database** (`backup_db.sh:8`) and can produce a silently short backup. Both `cleanup_low_est_rows.py` and `repair_pricing.py` route around it privately with the SQLite backup API.
6. **Trello #143 — the racy xAI counter.** Three `XaiTokenManager` instances writing one state file. #346 works around it with an on-disk floor rather than fixing it.
7. **Rows with no used offer keep their old prices.** `_process_single_deal` returns `None` when it finds no used offer, so the row is skipped, stays stale, and keeps whatever it had. `0851514014` in both runs. They accumulate in the SKIPPED manifest and need a separate decision.
8. **Option (e) routing** — repair on next touch, as a permanent net so nothing can go stale-priced again. Deferred by owner decision to its own PR.
9. **The 240-hour window and the IQR at `n <= 3`.** Both still inflate prices, and every row this sweep repairs carries them. **Each needs a `PRICING_LOGIC_VERSION` bump plus a re-sweep** — which is exactly what the version column was built for: change the logic, bump the constant, re-run the same script.

---

## 8. Infrastructure Findings

Facts established by test or by reading source this session, written down nowhere else in the repo.

**The schema migration runs on the first web request, not at deploy.** `create_deals_table_if_not_exists` has exactly two callers: `wsgi_handler.py:2961` (`@app.before_request`, behind the `_db_initialized` flag at `:2959`) and `smart_ingestor.py:311`. `deploy_update.sh` restarts services; it does not migrate. So a new `headers.json` column exists only after the first request or the first ingestion cycle, and anything run in that window fails on a missing column in a way that looks like a broken migration.

**The heavy path is unreachable for an existing ASIN by any normal means.** `smart_ingestor.py:577` routes on `asin in existing_asins_set` alone — there is no freshness, version or damage condition. This is the single fact that makes a separate repair script necessary rather than merely convenient.

**`last_price_change`'s `csv` branch is dead on every path, not just the repair's.** `stable_deals.py:211` takes `(deal_object, logger_param=None, product_data=None)` and the generic loop calls it as `func(product_data)` — one positional argument. The merged dict binds to `deal_object`; the `product_data` parameter stays `None`; the branch that reads it never runs. Same mechanism AGENTS.md §7.3 records for `last_update`, now confirmed for a second function. Its `currentSince` fallback is the only live path.

**Exactly two columns depend on the /deal feed object.** Established by running all 67 non-`None` `FUNCTION_LIST` entries twice against one fixture, with and without the deal keys — not by grep alone. `Deal_found` and `last_price_change`. Every direct read in `_process_single_deal` (`asin`, `title`, `manufacturer`, `fbaFees`, `referralFeePercentage`, `offers`, `categoryTree`) is a /product key.

**The Keepa token reservation is transient, not a spend.** `request_permission_for_call` reserves via `incrbyfloat` (`token_manager.py:324`); `update_after_call` then overwrites the bucket with Keepa's authoritative `tokensLeft` (`:545`, `:560`). Over-reserving costs nothing permanently — it only depresses the bucket between the reserve and the response, which is where Recharge Mode can be tripped. This corrects the throughput model in the previous day's planning report.

**`XaiTokenManager`'s state path is relative**, defaulting to `'xai_token_state.json'` against the process's CWD, and its count is read from disk **once**, at construction. Any long-running process's view of the daily count therefore diverges from the shared file as other processes write it. Both facts are load-bearing for #346's guard.

**A patched `fetch_targets` with no terminating `side_effect` hangs the test suite**, because the unlimited `--apply` loop relies on the real function honouring the attempted set to terminate. Two tests span until the mock's call list exhausted memory. Diagnosed with `faulthandler.dump_traceback_later`, which is the fastest way to find a spin inside pytest. Recorded because the symptom — a silent 120-second timeout with no output — reads like an environment problem and is not.

---

## 9. Files Modified

**PR #345 (merged) — the version column and the sweep:**

| file | change |
| :--- | :--- |
| `keepa_deals/pricing_version.py` | new — the constant, the NULL rule, the stale predicate |
| `repair_pricing.py` | new — the sweep |
| `keepa_deals/processing.py` | stamp the version in `_process_single_deal` |
| `keepa_deals/headers.json`, `keepa_deals/field_mappings.py` | the column and its index-aligned `None` slot |
| `keepa_deals/db_utils.py` | `"Version"` added to the INTEGER type rule, in both copies |
| `tests/test_pricing_logic_version.py`, `tests/test_repair_pricing.py` | new |
| `AGENTS.md` §7.13, `Data_Logic.md`, `System_Architecture.md`, `System_State.md` | the column, the rule, the runbook |

**PR #345 review fixes (`6fee8dc`, `739f048`):** deal-feed carry-forward allowlist and per-run attempted set in `repair_pricing.py`; `headers.json` re-indentation reverted to a one-line diff; unbounded dry run refused.

**PR #346 (merged) — the xAI headroom guard:**

| file | change |
| :--- | :--- |
| `repair_pricing.py` | `xai_calls_remaining`, the pre-batch guard, `--xai-headroom`, the CWD preflight check |
| `tests/test_repair_pricing.py` | `TheSweepStopsBeforeTheXaiCapIsHit`, 9 tests |
| `AGENTS.md` §7.13, `System_State.md` | the cap bounds the sweep at 8–10 days |

**PR #347 (merged) — the key redaction:**

| file | change |
| :--- | :--- |
| `keepa_deals/keepa_api.py` | `redact()`, applied to all ten error logs |
| `tests/test_keepa_api_key_redaction.py` | new, 11 tests |

**Suite:** 168 → 205 (#345) → 225 (review fixes) → 234 (#346) → 236 (#347).
