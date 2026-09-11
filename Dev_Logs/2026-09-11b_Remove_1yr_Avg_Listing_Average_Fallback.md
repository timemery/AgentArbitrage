# Dev Log Entry: Remove the `1yr. Avg.` Listing-Average Fallback (Audit B-6), and What the Diagnostic Found

**STATUS BLOCK**
- **Shipped:** PR #336 — fallback removed from `new_analytics.py`, dead `"Low (Est.)"` branch removed, `Inferred_Sale_Count` added (heavy path only), `cleanup_low_est_rows.py`, `diagnose_inferred_sales.py`, `recover_damaged_deals.py` archived, 6 docs updated, 42 new tests.
- **Live:** merged, main fast-forwarded `90e75c6 → e94f0c0`. Cleanup run 19:46:05 UTC, `deploy_update.sh` clean. `Inferred_Sale_Count` present in the live table (cid 247, INTEGER) after the first dashboard load — no manual migration, as predicted.
- **Ran:** 619 rows deleted in one transaction (dry run 619, backup verified at 4,160 rows). `Low (Est.)` now **0**. Backup and ASIN list in `db_backups/`.
- **Diagnostic:** 3 ASINs, **6 tokens each, not the ~20 I estimated**. Step-up mechanism **confirmed live on 5 of 7 sales**; far-gap on 1 (60.3 days). All three inflated `List_at` values are artifacts.
- **The $699 row is the two-sale case, not a hallucination.** Stored 699.11 = mean(699.99, 698.23), exactly the identity flagged in Phase 1 Q4a.
- **My diagnostic drew a wrong conclusion on a live ASIN** and Tim caught it: "not in the history → xAI" ignores that `1yr. Avg.` is a mean. Fixed in this PR.
- **User-visible:** ~2 rows removed from the dashboard. Inflated prices on existing rows are untouched and remain wrong.
- **Next:** test-suite trustworthiness first, then the inference fix, then a recovery plan for rows already carrying inflated prices.

**Date:** September 11, 2026
**Files:** see §9
**Status:** SUCCESS — MERGED TO MAIN (PR #336), RUN ON THE BOX, VERIFIED. Follow-up PR carries this log and the diagnostic correction.

---

## 1. Task Overview

Audit item **B-6**, settled by owner decision on 09-11: `1yr. Avg.` and `List at` come only from inferred sale prices. No fallback, no listing price, no list price, ever.

Phase 1 was read-only analysis of every fallback in the pricing chain. Phase 2 shipped the removal plus four things the analysis showed were needed alongside it: a way to tell how many sales a price rests on, a cleanup for the rows the fallback had already produced, a diagnostic to explain the $699 row, and the retirement of a script the change made unsafe.

The diagnostic then produced the most important result of the session, and it is not the fallback: **the inferred sale prices themselves are wrong on a class of deals**, by a mechanism Tim proposed and the box confirmed.

---

## 2. Premises That Turned Out Wrong

**(a) "The `avg365` fallback is the biggest hole in the pricing chain."** — implied by the B-6 framing, mine included. Wrong by an order of magnitude, and the diagnostic is what showed it. The fallback only ever reached `Percent_Down` and the Advisor's headline discount; `Profit` was never affected. The step-up defect (§4) reaches `List_at` directly, and therefore `Profit`, `Margin` and `ROI`. B-6 was worth doing and is now done, but it was the smaller problem.

**(b) "The diagnostic costs about 20 tokens per ASIN."** — mine, in the Phase 1 answer and the PR run steps. **Actual: 6.** I took the Smart Ingestor's own budget line (`20 * len(sub_batch)`, `smart_ingestor.py:550`) as the real cost. It is a conservative reservation for the token bucket, not what Keepa charges. Three ASINs cost 18 tokens, not 60.

**(c) "A stored value absent from the price history points at an xAI-invented sale."** — mine, written into `check_stored_price` and into the module docstring. **Wrong, and it fired on a live ASIN.** Tim caught it on 1429097078: the stored $699.11 is `mean($699.99, $698.23)`, an average of two prices that *are* in the history. `1yr. Avg.` is a mean and the sparse `List at` a median, so an average of real prices is usually not itself a real price, and absence proves nothing. Corrected in this PR (§5b) — the derived values are now computed and compared before xAI is named. Worth recording plainly: a diagnostic that draws a confident wrong conclusion is worse than one that draws none, because it sends the next investigation in the wrong direction.

**(d) "A leaked fallback row needs all its sales older than 365 days to be visible."** — jointly, deciding to skip the exception hole. Still true, but the diagnostic makes the boundary less comfortable than it sounded: sale sets shift as history is re-fetched, so a row can move between "has in-year sales" and "does not" over time. It does not change the decision; it does mean the leak count cannot be treated as frozen.

**(e) "The Amazon ceiling is the next thing to look at after B-6."** — mine, Phase 1 Q1. Demoted. On 1429097078 there is no Amazon price at all, so the ceiling never engages; on all three diagnosed ASINs the damage is upstream of it. The ceiling is still wrong, but it is now behind the inference fix in priority.

---

## 3. Hypotheses Raised and Discarded

**3.1 "Reject new deals with zero inferred sales instead of persisting them."** REJECTED, owner decision, and the arithmetic backs it. Rejecting returns the ASIN to `new_candidates` on every appearance in the deal feed at 20 reserved tokens per heavy re-fetch, against 5 for a light update. Rejection costs more per cycle and re-creates the loop AGENTS.md §7.8 persistence exists to stop. The real cost of dead rows is not tokens but **queue slots**: `rescue_stale_deals` takes a fixed `LIMIT 20` per run (`smart_ingestor.py:199`, `:226-232`), so dead rows crowd live ones out of a fixed queue. That needs an expiry policy, not a change to reject/persist.

**3.2 "Blank the fallback rows in place (`UPDATE ... SET 1yr_Avg = NULL`) rather than delete."** REJECTED, owner decision. It kills the bad number without spending re-acquisition, but leaves 619 permanently invisible immortal rows — exactly the queue-slot problem in 3.1.

**3.3 "Fix the swallowed-exception hole in `processing.py:220-253` in the same PR."** REJECTED, owner decision, with the reasoning recorded because it is not obvious: with the fallback gone there is nothing left to leak. The hole only mattered because it let a fallback row escape the `"Low (Est.)"` marker, and no code path writes a fallback value any more. It stays an open item on its own merits.

**3.4 "Keep `recover_damaged_deals.py` and amend its invariant."** REJECTED. Its predicate rationale (`System_Architecture.md` §3.E) rested on `1yr_Avg IS NULL` being a reliable damage fingerprint, and this change retires that premise wholesale rather than adjusting it. Amending the invariant would leave a delete script documented against a world that no longer exists. Archived instead.

**3.5 "Reduce the test fixtures to make the end-to-end tests fast."** REJECTED after measuring. Cutting the mock history 4× changed the runtime not at all — it was a fixed 10.0s, which is what led to the `last_update` retry finding in §8. The fixtures were left honest and `retrying.time.sleep` stubbed instead.

**3.6 "The $699.11 came from the xAI rescue."** DISPROVEN on the box. It is two algorithmic sales averaged. See §4b.

---

## 4. Root Cause

### 4a. The fallback (B-6) — what shipped

The March 2026 removal of the "Keepa Stats Fallback" covered `stable_calculations.py` only. A second fallback survived in `new_analytics.py` on the `1yr. Avg.` path and fired for six months. It was **strictly more aggressive than the one deliberately deleted**: the Silver Standard took `min(avg90, avg365)` on the Used index alone, this one built candidates from five `avg365` condition tiers and took `max`. On the audit's worked example a true $31.00 became $88.00, turning a 16% discount into a reported 70% one, fed verbatim to Ava (`ava_advisor.py:466-467`) and Prime Picks Pass 1.

### 4b. The leftover asking price — what the diagnostic found

Tim's hypothesis, confirmed live. `csv[1]` and `csv[2]` hold the **lowest** New / Used offer price, not the price of any particular copy. When the cheapest copy sells, the series does not record what it sold for — it steps **up** to whatever the next cheapest listing asks, at essentially the same timestamp as the offer-count drop that marks the sale. `merge_asof(direction='nearest')` (`stable_calculations.py:302`) has no tolerance and no tie-break, so it can land on the point **at or after** the drop and store the asking price of a copy that did **not** sell.

Live results, 3 ASINs, 7 confirmed sales:

| ASIN | sales | before → recorded | verdict |
|---|---|---|---|
| 1890919489 | 1 | $124.85 → **$1,000.00** | step-up |
| 1468308963 | 1 | $49.95 → **$499.95**, gap 60.3 days | far-gap *and* step-up |
| 1429097078 | 5 of 11 drops | $328.19 → $625.59; $54.33 → $85.39 (IQR trimmed); $85.39 → $700.00 | 3 step-ups |

**5 of 7 sales show the step-up. All three inflated `List_at` values are artifacts.** The round numbers on the box — `$1,000.00`, `$499.95` on three deals, `$250.00`, `$200.00`, `$150.00` — are prices a seller typed into a listing, not prices anything transacted at.

**The $699 row is a different and quieter failure.** Its two highest "sales" ($699.99 on 03-22, $698.23 on 05-18) are **not** step-ups: the lowest Used listing sat near $700 both before and after each drop. Those look like **listing removals that happened to coincide with an unrelated rank drop inside the 240-hour window** — a false positive in the confirmation rule itself, not in the price association. Stored `1yr_Avg` 699.11 = `mean(699.99, 698.23)`: the two-sale case flagged in Phase 1 Q4a, where median and mean coincide for any two in-year sales, which is why `List_at` and `1yr_Avg` were identical. Current used is $25.00. Today's code would still produce `1yr Avg` **$680.95**.

So there are at least **three** distinct defects producing inflated prices, and only the third is the one originally suspected: price association picking the post-sale asking price; rank-confirmation accepting an unrelated rank drop within 240 hours; and, at `n ≤ 3`, an IQR that cannot trim anything and in fact trimmed the one *plausible* low sale ($85.39) because the inflated ones dominated the quartiles.

---

## 5. The Fix

### 5a. PR #336 (merged)

**`new_analytics.py`** — the `avg365` candidate block deleted. Zero inferred sales inside 365 days returns `None`. The deal is persisted with a NULL `1yr_Avg` and filtered from the dashboard, not rejected.

**`processing.py`** — the dead `"Low (Est.)"` branch removed. **`stable_calculations.py`** — the `'Keepa Stats Fallback'` half of the AI-check skip removed. The sparse half and **every** `Deal_Trust` CAST left untouched: `deal_trust()` still returns `'-'` when `total_offer_drops == 0`, and the CAST exists for that state.

**`Inferred_Sale_Count`** — returned on every branch of `analyze_sales_performance` including the zero-sale rejection, so `0` ("computed, none found") is distinguishable from `NULL` ("never computed"). Heavy path only. No filter reads it.

**Schema, no manual step.** `create_deals_table_if_not_exists()` runs at `smart_ingestor.py:311`, before both upsert sites, and ALTERs in any `headers.json` column the live table lacks. Verified against a temp database built without the column before the run, and confirmed on the box afterwards (cid 247, INTEGER).

**`cleanup_low_est_rows.py`** — predicate `"Deal_Trust" = 'Low (Est.)'`, the only persisted fingerprint (`price_source` is computed but never stored; it is not in `headers.json`, so `upsert_deal_rows` drops it). Invariant chosen to survive this change: zero rows with the marker **and** a NULL `1yr_Avg`.

**`recover_damaged_deals.py` archived** to `Archive/scripts/`. Its invariant asserted zero rows with `"1yr_Avg" IS NULL AND "List_at" IS NOT NULL`; this change makes that legal — `List at` uses a 3-year window, `1yr. Avg.` a 1-year one — so a book whose sales are all older than 365 days now has exactly that shape. The script would abort on a healthy database and tell the reader to investigate something correct.

**Tests: 42 new.** Three fail on the parent commit, returning exactly the `$88.00` the audit predicted. The pre-existing `test_1yr_avg_logic.py::test_insufficient_data_old_sales` looked like it already covered this and did not: its mock has no `stats` key, so the fallback bailed at `if not stats` without reaching the candidates. Every new mock carries a populated `stats.avg365`.

| full suite, same environment | main | PR #336 |
|---|---|---|
| passed | 56 | 94 |
| failed | 26 | 26 |

Identical failure set, no new failures. The 26 are pre-existing (§8).

### 5b. Follow-up PR (this one): the diagnostic's wrong conclusion

`check_stored_price` concluded that a value absent from the price history "points at an xAI-invented event" (premise (c)). It now computes the derived candidates first — the mean of in-year sales and, on the sparse branch, the median of all sane sales — and names xAI only when the stored value is **neither** in the history **nor** derivable. On the 1429097078 shape it correctly reports a computed average and says so:

```
  1yr Avg: mean of the 2 sale(s) inside 365 days       $699.11   <-- MATCHES STORED
  The stored value is a COMPUTED average, not a recorded price, so
  its absence from the history is expected and is not evidence of anything.
```

Three tests pin it, including the live case that caught it. No pricing code touched.

---

## 6. Deployment Result

PR #336 merged, main fast-forwarded `90e75c6 → e94f0c0`.

**19:45 UTC** — `kill_everything_force.sh`, then the dry run. Backup verified at **4,160 rows**; invariant check passed; **619 targets** (`smart_ingestor` 35, `smart_ingestor_light` 7, `stale_rescue` 577), **2 visible** on the dashboard.

**19:46:05 UTC** — `--apply`, 619 deleted in one transaction.

| source | after |
|---|---|
| smart_ingestor | 136 |
| smart_ingestor_light | 68 |
| stale_rescue | 3,337 |
| **ALL** | **3,541** |
| **`Low (Est.)`** | **0** |

Backup `db_backups/deals.db.low-est-20260911-194605.bak`, ASIN list `db_backups/low_est_asins_applied_20260911-194605.txt`. `deploy_update.sh` clean. `Inferred_Sale_Count` present in the live table after the first dashboard load.

Target was 619 against the 618 measured in Phase 1 — one row acquired the marker between the two measurements, which is the fallback still firing on the pre-merge code. Consistent, not anomalous.

**Read the source counts with the standing caveat:** the light path rewrites `source`, so rows migrate between cohorts and a changed count is not evidence of deletion.

---

## 7. Open Items

Priority order, owner-set.

**1. Make the test suite trustworthy. One small PR, first.** Two defects, both in §8. `run_tests.sh` cannot currently gate anything, which is a precondition for everything below it.

**2. The pricing inference fix.** Take the price from the last point **before** the offer drop instead of `merge_asof` nearest; add a time tolerance; review the 240-hour rank-confirmation window (§4b shows it accepting unrelated rank drops); and address the IQR, which gives no protection at `n ≤ 3` and can trim the true low sale when inflated ones dominate the quartiles. Blocked on two owner decisions still open: Grok-picked sales, and minimum sale count versus a UI flag.

**3. A recovery plan for rows already carrying inflated prices.** This is the one that decides when the dashboard is trustworthy again. **A fix to the inference does not repair a single existing row**, because the light path never recomputes `List_at` or `1yr_Avg` and the recalculator is API-free. Re-fetch versus delete has to be decided before the numbers on screen can be relied on.

**4. Carried forward.** Amazon ceiling clamp and the A-10 AI-check bypass. Blank **Ago**, 893 visible rows. Expiry policy for permanently incomplete rows, covering the 1,671 `List_at`-NULL rows. The swallowed exceptions in `get_trend` and `analyze_sales_rank_trends`. `POST /api/run-janitor` auth. Fee and settings defaults. `backup_db.sh` copying a WAL database with `cp`.

---

## 8. Infrastructure Findings

**Every newly discovered deal wastes 10 seconds of wall clock.** `field_mappings.py:479` puts `stable_deals.last_update` in `FUNCTION_LIST`, but its signature is `last_update(deal_object, logger_param, product_data=None)` (`stable_deals.py:114`) and `logger_param` has no default. The generic loop at `processing.py:123-135` calls every field function as `func(product_data)`, one positional argument, so it raises `TypeError` on **every** call. It carries `@retry(stop_max_attempt_number=3, wait_fixed=5000)` (`stable_deals.py:113`), so each heavy-path deal burns two 5-second sleeps and then stores nothing for that column. Its sibling `last_price_change` (`stable_deals.py:189`) survives only because its `logger_param` does have a default. Found by profiling, not reading — the end-to-end tests were a fixed 10.0s regardless of fixture size (§3.5). This is a throughput bug, not slowness.

**The test suite poisons itself.** `tests/test_approve_dedup.py:12-16` assigns `MagicMock()` into `sys.modules` for `flask`, `celery_app`, `keepa_deals.db_utils`, `keepa_deals.janitor` and `keepa_deals.ava_advisor` at import time and never restores them. pytest imports every test module before running any test, so those mocks are live for the whole session. That is the cause of all **26** pre-existing failures, including `tests/test_lightweight_upsert_preservation.py` — the guard `AGENTS.md` §7.12 says must stay green, which passes 12/12 alone and fails in-suite. The new tests sidestep it via `tests/_real_module.py` rather than depend on collection order; the underlying defect is untouched.

**Keepa's real per-ASIN cost is 6 tokens, not 20** for `fetch_product_batch(days=365, history=1, offers=20)`. The 20 in `smart_ingestor.py:550` is a token-bucket reservation. Any capacity planning that used 20 as the true cost is roughly 3× pessimistic.

**The diagnostic mirrors `infer_sale_events` by hand** and must be kept in sync — it re-implements rather than calls, because `infer_sale_events` invokes xAI on both of its zero-sale branches. `tests/test_diagnose_inferred_sales.py::MirrorsProduction` pins it against production on four histories. A drifted mirror does not fail loudly; it prints a confident wrong answer, which is exactly what premise (c) did.

---

## 9. Files Modified

**PR #336 (merged):**

| file | change |
|---|---|
| `keepa_deals/new_analytics.py` | `avg365` fallback removed from `get_1yr_avg_sale_price` |
| `keepa_deals/processing.py` | dead `"Low (Est.)"` branch removed; `Inferred Sale Count` written |
| `keepa_deals/stable_calculations.py` | `'Keepa Stats Fallback'` removed from the AI-check skip; `inferred_sale_count` on every return branch |
| `keepa_deals/headers.json` | `"Inferred Sale Count"` appended |
| `keepa_deals/field_mappings.py` | matching `None` slot, index alignment preserved |
| `cleanup_low_est_rows.py` | new |
| `diagnose_inferred_sales.py` | new |
| `Archive/scripts/recover_damaged_deals.py` | moved from repo root |
| `Archive/scripts/test_recover_damaged_deals.py` | moved from `tests/` |
| `Archive/scripts/README.md` | new |
| `tests/test_1yr_avg_no_fallback.py` | new, 13 |
| `tests/test_cleanup_low_est_rows.py` | new, 19 |
| `tests/test_diagnose_inferred_sales.py` | new, 10 |
| `tests/_real_module.py` | new, sidesteps the `sys.modules` pollution |
| `Documentation/INFERRED_PRICE_LOGIC.md` | Critical Warning, §4B, new §4C |
| `Documentation/Data_Logic.md` | `1yr. Avg.`, Deal Trust, `List at`, AI-skip; 2 pre-existing errors corrected |
| `Documentation/Dashboard_Specification.md` | `1yr Avg`, Min. Deal Trust; the undocumented `'-'` state |
| `Documentation/System_Architecture.md` | §3.E rewritten to cover both scripts |
| `Documentation/System_State.md` | March 2026 entry marked complete |
| `AGENTS.md` | §7.1 September 2026 addendum |

**This PR:**

| file | change |
|---|---|
| `diagnose_inferred_sales.py` | `check_stored_price` no longer blames xAI for a computed average; docstring corrected |
| `tests/test_diagnose_inferred_sales.py` | 3 tests for the corrected conclusion |
| `Dev_Logs/2026-09-11b_Remove_1yr_Avg_Listing_Average_Fallback.md` | this entry |
