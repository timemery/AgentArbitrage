# Dev Log Entry: Remove the xAI Sales Rescue, and Teach the Diagnostic to Compute the Boring Answer First

**STATUS BLOCK**
- **Shipped:** PR #342 — the xAI sales rescue removed from both zero-sale branches of `infer_sale_events`, 12 new tests pinning the absence, 6 docs updated (incl. the customer-facing overview), plus review follow-up `701e888`. PR #343 — `diagnose_inferred_sales.py` now reconstructs the pre-fix value before naming history drift or xAI, 8 new tests.
- **Live:** merged `ddd8c15`. Box fast-forwarded `4166e03 → ddd8c15`, `deploy_update.sh` clean at **20:53 UTC**, Recharge Mode 60 min.
- **PR #340 verified first, and it holds.** 3,061 rows touched since `2026-09-12T16:45:14`; 592 carry an `Inferred_Sale_Count`; those heavy rows average **$101.66** against the **$126.10** pre-fix baseline and top out at **$521.50**. No four-figure price has been written by post-fix code.
- **"There is a cap making every rescue return 1 sale" was wrong.** No cap exists — `xai_sales_inference.py:244-260` has no break and no slice. The 100-day window, the silent N=0 case and a 500-token budget on a reasoning model explain it between them. §2(a).
- **"13 rescues" was wrong too.** The real pre-deploy count is **18** branch-2 rescues and **0** branch-1 — and they are only **5 distinct ASINs**, because `infer_sale_events` runs **5× per heavy deal** with no memoisation. §2(b), §8.
- **Deal Trust was quietly corrupted by the rescue**, not just the price: one model event over N *failed* offer drops read as 1/N. Two failed drops read 50% and cleared the Agent's Choice floor of 40. Now a truthful 0%.
- **User-visible:** nothing today. Pre-fix rows are untouched — the top 30 rows over $500 are all `stale_rescue` with a NULL count, kept alive but never re-priced. Suite 148 → 160 (#342), 148 → 156 (#343).
- **Next:** Trello #139, the recovery sweep for those rows. Plan approved; `Pricing_Logic_Version` + `repair_pricing.py`.

**Date:** September 16, 2026
**Files:** see §9
**Status:** SUCCESS — BOTH MERGED TO MAIN (PR #342, PR #343). This entry is the docs-only follow-up.

---

## 1. Task Overview

Trello #141, plus the exclusion decision it carried. Two phases, the first read-only and ending in a report that had to be approved before any code moved.

The question was narrow: when `infer_sale_events` found zero confirmed sales it called xAI, and production logs showed every rescue returning exactly one sale. Was that a cap, and should the rescue exist at all?

Phase 1 answered both. Phase 2 implemented option (a) — stop calling it — on Tim's decision. A separate PR then fixed a wrong conclusion the diagnostic had been printing, caught on a live ASIN the same day.

Scope was fenced and held: the 240-hour rank-confirmation window, the IQR at `n <= 3`, any minimum sale count or UI flag, the Amazon ceiling clamp, recovery of existing rows (#139), log rotation (#140), boot persistence (#142) and the xAI token counter (#143) were all out of bounds and none were touched.

Sequencing mattered and was deliberate: #139 is a heavy re-fetch of existing rows, and those rows would have gone through whatever rescue behaviour was left in place. Removing the rescue first means #139 repairs rows rather than re-rolling them.

---

## 2. Premises That Turned Out Wrong

**(a) "Every rescue returns exactly 1 sale, so something caps it."** — the brief, offering the parse loop around `:260` as the prime suspect. **Wrong. There is no cap anywhere.**

`keepa_deals/xai_sales_inference.py:244-260` iterates the full `events` list with no `break`, no slice and no `[:1]`, and appends every event that parses. The prompt (`:170-178`) asks for a list and sets no limit. Both call sites returned `xai_sales` verbatim. The count of 1 was real, not imposed. Three things produce it together:

| cause | evidence |
| :--- | :--- |
| The rescue saw only **100 days** | `xai_sales_inference.py:235` `format_history_for_xai(product, days=100)` — against the algorithmic path's **1095** at `stable_calculations.py:227` |
| **N=0 is silent** | `:262` `if confirmed_sales:` guards the log; a zero-event rescue returns `None` at `:266` with no line at all |
| **`max_tokens: 500`** on a reasoning model | `:193` — reasoning consumes the completion budget, so a long event list truncates mid-JSON, fails `json.JSONDecodeError` at `:210` and is discarded whole |

The input population is, by definition, ASINs with zero algorithmic sales across three years — the slowest movers in the feed. Asking that population about 100 days yields 0 or 1, and only the 1s are logged. **"Every rescue returned 1" was a selection effect on a silent denominator, not a defect in the loop.**

Recorded because the brief's suspicion was reasonable and specific, and checking it took one read of the loop. The wrong instinct was to assume a suspiciously round result must have a mechanism enforcing it.

**(b) "13 rescues, 2026-08-28 to 2026-09-08."** — the brief, from a `grep` on `:263`. **The real figure is 18, and it is 5 ASINs, not 18 deals.**

The pre-deploy log (1,327,190 lines, starting 08-28) holds **18** branch-2 rescues and **0** branch-1 "(Hidden Sales)" rescues. The branch split is readable because the two sites log distinguishably one frame up — `stable_calculations.py:264` carried `(Hidden Sales)`, `:382` did not — which is what makes the zero meaningful: **the "no offer drops at all" branch never fired in production at all.** Every rescue came from "offer drops existed and none correlated", which is precisely the branch that also corrupted `Deal Trust`.

The 18 resolve to **5 distinct ASINs**, because `infer_sale_events` is called **5 times per heavy-path deal** and is not memoised (§8). So the rescue's blast radius per deal was 5 xAI calls, and the log line count overstates the number of affected deals by roughly that factor while understating the spend. Both readings of the raw count are wrong in opposite directions.

Three of the five survive in the DB: `1871083850` (visible, $72.98, Deal Trust 10%), `0731064372` and `B0DPN35JFP` (both `List_at` NULL). **Rescues before 08-28 are unrecoverable** — the log does not reach back, and nothing in the schema records which rows were rescued.

**(c) "A rescued sale comes from one unchecked number."** — the working assumption in the brief, to be verified. **Half right, and the half that was wrong matters.**

Bypassed: the IQR (`stable_calculations.py:389-404`, the rescue returned at `:265`/`:383` before it), the NaN guard (`:357`), and the `price <= 0` guard (`:365`). The rescue's only price check was `if date_str and price:` at `xai_sales_inference.py:250` — a truthiness test, which admits a *negative* price.

Still applied: the Amazon 90% ceiling (`:580-604`), the $1,500 hard ceiling (`:640-646`) and the 3×-current-used force (`:653-658`). So it was not "unchecked" — it was **unsanitised**, and conditionally un-AI-checked. The correction is worth keeping because it narrows the claim to something defensible.

The larger point the assumption missed entirely: **PR #340's price association never applied to a rescued sale at all.** A rescued price is not read from `csv[1]`/`csv[2]`; it is asserted by a model. It can be neither correctly nor incorrectly associated.

**(d) "The stored value did not come from today's code, so the history moved or it came from the xAI rescue."** — printed by `diagnose_inferred_sales.py` on ASIN `0415009804`, and **wrong**, which is what PR #343 fixes.

The script's own output already held the answer. Its step-up table reported 'old would' **$500.00** on sale 1 and **$-0.01** on sale 2. Pre-fix code would have discarded the second on its `price <= 0` guard and been left with one sale at $500.00, which at n=1 takes the sparse branch and stores its median — **exactly the stored $500.00**. Today's code gives $223.75. No history drift, no xAI. Confirmed on the box for 6 tokens.

**This is the second time this file has drawn a conclusion it had not earned.** On 2026-09-11 `check_stored_price` blamed xAI for a value that was just the mean of two real prices. Same shape: naming an exotic cause without first computing the ordinary one. A conclusion rule is now written into the module docstring, because the rule has been broken twice.

---

## 3. Hypotheses Raised and Discarded

**"Option (b) — keep calling the rescue, discard the result, log what it would have returned."** Offered in the Phase 1 report as the alternative to removal, on the grounds that it buys telemetry. **Discarded.** It leaves spend unchanged at up to 5 calls per zero-sale ASIN, so you pay in full for observability you can get free: `grep "(Hidden Sales)"` against existing logs already splits the rescues by branch, which is how §2(b)'s zero was established at no cost.

**"A non-NULL `Inferred_Sale_Count` proves a row is post-fix."** Tempting, and **false**. `0415009804` carries a count *and* a pre-fix price: rows priced between 09-11 (when the column shipped) and 09-12 16:50 (when #340 went live) have both. Confirmed on the box. This killed the only column that looked like it might date a row's pricing, and is why #139 needs a new one.

**"Rows with `1yr_Avg = List_at` identify the rescued ones."** Real fingerprint, useless as a selector — it matches legitimate 1-sale algorithmic deals just as well. `price_source` is computed (`stable_calculations.py:695`) but never persisted, so **there is no query that finds rescued rows.**

**"Delete the affected rows and let the feed rediscover them"** (raised while planning #139). **Discarded.** The rows kept alive by Stale Rescue are precisely the ones the deal feed has stopped returning, so deletion is permanent for exactly the population that most needs repair.

**"Patch the `recompute` conclusion to say 'possibly pre-fix'."** Considered for #343 and rejected as the same failure in a softer voice. A diagnostic that hedges is no more use than one that guesses; it had to *compute* the pre-fix value and compare.

---

## 4. Root Cause

**The rescue was a third source of unverified prices, surviving two removals aimed at exactly that class of input.**

March 2026 deleted the Keepa Stats Fallback from `stable_calculations.py`. 2026-09-11 (audit B-6) deleted the `avg365` fallback from `new_analytics.py`. Both were removed because a listing average is not a sale price. A model-asserted sale is the same error one layer further out: nothing checked that the price had ever appeared in the Keepa history at all.

It survived because it did not *look* like a fallback. It produced a `sale_events` list of the same shape as the real one, entered the pipeline through the same variable, and set `price_source = 'Inferred Sales (Sparse)'` — **the identical label a genuine 1-sale algorithmic deal carries**. Nothing downstream, and no column in the schema, could tell the two apart.

The consequences compounded rather than cancelled:

- At n=1 the Sparse Sales Rescue takes the median of one number, so `List at` and `1yr. Avg.` became the **same single model-asserted figure**.
- The rescue's 100-day window guaranteed the event fell inside 365 days, so `1yr_Avg` was always populated — meaning a rescued row **always** cleared `/api/deals`' data-completeness filter (`wsgi_handler.py:2254-2259`). **Rescued deals were, structurally, the ones subscribers saw.**
- On the only branch that fired in production, `Deal Trust` = `len(xai_sales) / total_offer_drops` put one invented event over offer drops that had *just failed to correlate with anything*. Two failed drops read 50%, above the Agent's Choice floor of 40 (`wsgi_handler.py:2231`).

---

## 5. The Fix

**PR #342.** Both call sites (`stable_calculations.py:262`, `:380`) and the import at `:19` removed. Zero confirmed sales is now a final answer on both branches.

| | before | after |
| :--- | :--- | :--- |
| zero-sale deal | rescued, priced from 1 model number | **persisted**, NULL `List_at` / `1yr_Avg` |
| `Inferred_Sale_Count` | 1 | **0** — "computed, none found", still distinct from NULL |
| `Deal_Trust`, no offer drops | `'-'` | `'-'` (unchanged) |
| `Deal_Trust`, drops all failed | **1/N** (50% at N=2) | **`0%`** — drops stay in the denominator |
| dashboard | visible | filtered out |

Deals are **persisted, not rejected** (AGENTS.md §7.8 — rejecting re-creates the 20-token re-fetch loop). Both requirements came for free from the existing returns at `:266` and `:385`: `inferred_sale_count = 0` and the offer-drop denominator were already correct on the zero-sale path.

`keepa_deals/xai_sales_inference.py` is kept — the dormant `Keepa_Deals.py` path references it — and now carries a docstring saying the live pipeline does not call it. `tests/test_xai_sales_inference.py` is relabelled as covering a module unused by the live pipeline.

**Measured, before and after.** The PR #340 verification run that preceded this work is the baseline against which #342's effect will be read:

| | rows | avg `List_at` | max |
| :--- | ---: | ---: | ---: |
| pre-#340 baseline | 2,598 priced | **$126.10** | four figures present |
| all rows touched since 09-12T16:45 | 3,061 | $122.22 | — |
| **of those, heavy (`Inferred_Sale_Count` present)** | **592** | **$101.66** | **$521.50** |
| top 30 rows over $500 | 30 | — | all `stale_rescue`, **all NULL count** |

The heavy-path cohort is the only one that post-fix code wrote, and it contains **no four-figure price**. Every remaining one is a pre-fix artifact that nothing has re-priced. That separation is what made #139's scope obvious.

**PR #343.** `reconstruct_prefix_value` replays the pre-fix pipeline on the 'old would' prices — only the *association* differed pre-fix, so the `price <= 0` guard, the IQR and the mean/median branch rules are replayed unchanged rather than approximated. `confirm_sales` also now returns rank-confirmed drops that today's code discards on price but the pre-fix match could still price; without them the reconstruction under-counts and can report "no match" for a row that is fully explained. The `0415009804` run now prints `THIS ROW PREDATES THE PRICE-ASSOCIATION FIX` and `ACTION: ... HEAVY RE-FETCH`, and names drift or xAI only when the reconstruction does not match.

**Tests.** `tests/test_xai_rescue_excluded.py`, 12 tests, **10 failing on the parent** — the two that pass on both deliberately pin unchanged behaviour. `PreFixReconstruction`, 8 tests, **all 8 failing on the parent**. Suite **148 → 160** (#342) and **148 → 156** (#343); `MirrorsProduction` green throughout.

**Review follow-up `701e888`.** Tim's review found three stale references #342 missed, all customer- or operator-facing: the product overview still sold "(d) AI rescue for hidden-sale detection ... all four" (now three, no replacement invented), and both `Dashboard_Specification.md` and `System_Architecture.md` described the `Deal Trust` `'-'` state as "the XAI no-offer-drops rescue" — it is not a rescue and never was, it is what `deal_trust` returns when a history holds no offer drop in three years. A repo-wide sweep then found three more: a **live code comment** at `stable_calculations.py` still describing an XAI-rescue path, and two test comments. **Worth recording: the code comment was the real miss.** The docs were reviewed; the comment inside the file being edited was not.

---

## 6. Deployment Result

Merged `#342` then `#343`. Box fast-forwarded `4166e03 → ddd8c15`, `deploy_update.sh` clean at **20:53 UTC**, Recharge Mode set for 60 minutes.

**Nothing changed on screen, and that is expected.** The change is heavy-path only, and the heavy path runs on *new* ASINs only — `smart_ingestor.py:577` routes purely on `asin in existing_asins_set`. No existing row is repaired. Verification is the same shape as #340's: new deals accruing against a baseline over days, not a same-day check.

**What to watch:** the `592`-row heavy cohort should keep its ceiling near $521 and should now also show `Deal_Trust = '0%'` rows where it previously showed small non-zero percentages from rescued events. The three surviving rescued ASINs (`1871083850`, `0731064372`, `B0DPN35JFP`) will not change until #139 reaches them.

**Sizing taken at deploy**, which sets #139's scope:

| | |
| :--- | ---: |
| total rows | 4,534 |
| priced (`List_at > 0`) | 3,070 |
| `Inferred_Sale_Count` NULL / present | 3,541 / 993 |
| visible (dashboard predicate) | 1,100 |

| `List_at` band | rows |
| :--- | ---: |
| < $50 | 1,281 |
| $50–150 | 985 |
| $150–400 | 658 |
| $400–1000 | 129 |
| **≥ $1000** | **17** (avg **$1,155.91**) |

Those 17 are the visible damage. All pre-fix.

---

## 7. Open Items

1. **Trello #139 — the recovery sweep.** Plan written and approved this session: add `Pricing_Logic_Version`, then a one-off `repair_pricing.py` heavy-re-fetching every row where the version is NULL or behind. ~4,534 rows, days of wall clock. **Nothing in the schema dates a row's pricing today** (§8), which is the whole reason the column is needed.
2. **The 240-hour rank-confirmation window** accepts rank drops unrelated to the offer drop. Still open, still inflating prices. Every row #139 repairs will carry this.
3. **The IQR gives no protection at `n <= 3`.** Same. Both will need their own re-fetch — which is why #139's selector is a *version*, so a future fix re-runs the same tool by bumping a constant.
4. **Rescued rows before 2026-08-28 are unidentifiable.** No column records them, the log does not reach back, and the `List_at = 1yr_Avg` fingerprint also matches legitimate 1-sale deals. Only a full sweep clears them, which argues against repairing a visible subset only.
5. **A minimum-sale-count floor is not enforceable yet.** `Inferred_Sale_Count` is NULL on 3,541 of 4,534 rows, and the documented rule is that NULL must never be read as zero or used to hide a deal. After a full heavy sweep every surviving row has a real integer and the floor becomes a one-line `WHERE`.
6. **`backup_db.sh` is a plain `cp` of a WAL-mode database** (`backup_db.sh:8`) and can produce a silently short backup. `cleanup_low_est_rows.py:243-295` routes around it privately. Deserves its own card.
7. **#143, the racy xAI daily counter.** Three `XaiTokenManager()` instances writing one state file. Carded, untouched.

---

## 8. Infrastructure Findings

Facts established by test or by reading source this session, written down nowhere else in the repo.

**`infer_sale_events` runs 5× per heavy-path deal, and is not memoised.** `keepa_deals/processing.py:144`, `processing.py:235` → `new_analytics.py:73`, `stable_calculations.py:455` (`recent_inferred_sale_price`), `:759` (`_get_analysis`) and `:804` (`deal_trust`). Only the fourth is cached. While the rescue existed this meant **up to 5 xAI calls per zero-sale ASIN**, which is why 18 log lines are 5 deals. It also means the full correlation loop — three DataFrame constructions, the 3-year filter and the per-drop search — runs five times per deal today, for free, on every heavy pass. Not a defect this task was scoped to fix, but it is the multiplier behind every per-deal cost estimate in #139.

**`_analysis_cache` is memoised by ASIN for the life of the process, and `clear_analysis_cache` has no production caller.** `keepa_deals/stable_calculations.py:742-747`, `:756-764`. The only `grep` hit outside its own definition is nothing. In a long-lived Celery worker a previously-analysed ASIN returns a stale analysis indefinitely. Harmless for a one-off script in its own process — and a reason to prefer a script over a Celery task for #139 — but a live hazard for anything that re-prices inside the worker. Out of scope here; noted so the next person does not discover it the hard way.

**`confirm_sales` in `diagnose_inferred_sales.py` now returns a 3-TUPLE.** `diagnose_inferred_sales.py:244` (def), `:250` (early return) and `:422` (`return confirmed, rejected, legacy_only`). **This supersedes the fact recorded in `2026-09-12b` §8**, which stated it returns a 2-tuple of `(confirmed, rejected)` and relied on that shape for the box measurement it describes. The third element carries rank-confirmed drops whose price today's code discards but the pre-fix nearest-match could still have priced. Any ad-hoc box command copied from that entry will now raise `ValueError: too many values to unpack`.

**Nothing in the schema dates a row's pricing.** Checked every timestamp and marker column. `last_seen_utc` and `source` are both rewritten by all three paths — heavy `smart_ingestor.py:580-581`, light `:574-575`, Stale Rescue `:274-275` — so `source` records **who touched the row last, not who priced it**. `Deal_found` is Keepa's `creationDate` (`stable_deals.py:83`), not a write time. `last_update` is deliberately NULL (`FUNCTION_LIST[10]`). `Inferred_Sale_Count` is disproved by `0415009804`. This is the finding that makes #139's version column unavoidable rather than merely convenient.

**The heavy path fully overwrites an existing row, NULLs included.** `build_deals_upsert` (`db_utils.py:67-87`) emits `ON CONFLICT(ASIN) DO UPDATE SET` for every column from `headers.json`, and `upsert_deal_rows` binds `row.get(col)` for each (`:105`) — **a key absent from the row binds NULL**. `List_at` reaches NULL via the FUNCTION_LIST loop (`processing.py:123-133` assigning `None`); `1yr_Avg` reaches it by key absence (`processing.py:235-238` does not set the key when the value is None). So a re-fetch that now finds zero sales correctly produces a NULL-priced, `Inferred_Sale_Count = 0`, persisted, hidden row. **#139 does not need any special write path.**

**The xAI reasonableness cache cannot serve a stale verdict after a re-price.** `stable_calculations.py:65` keys on `price_usd:.2f` alongside rank and trend, so a changed price is a different key. Checked because a repaired row passing an old verdict would have been a silent correctness hole in #139.

**`prime_picks` stores selection, not prices.** `prime_picks_task.py:406-409` stores `asin, rank, score, generated_at, run_id`; `wsgi_handler.py:2346` joins back to `deals` for display, so prices shown are live. But the *selection* was made against pre-fix prices and the task is **not** beat-scheduled, so it will not self-heal — #139 must end by refreshing it.

---

## 9. Files Modified

**PR #342 (merged) — remove the rescue:**

| file | change |
| :--- | :--- |
| `keepa_deals/stable_calculations.py` | both rescue call sites and the import removed; block comment recording why |
| `keepa_deals/xai_sales_inference.py` | module docstring: not called by the live pipeline; kept for the dormant path |
| `tests/test_xai_rescue_excluded.py` | new — 12 tests pinning the absence |
| `tests/test_xai_sales_inference.py` | relabelled as covering an unused module |
| `tests/test_price_association.py`, `tests/test_1yr_avg_no_fallback.py`, `tests/test_diagnose_inferred_sales.py` | five `infer_sales_with_xai` patch sites removed |
| `AGENTS.md` | §7.1 September 2026 Addendum 2; §7.8 Sparse Sales Rescue clarified |
| `Documentation/Data_Logic.md` | rescue bullet, `Inferred_Sale_Count`, `Deal Trust` non-numeric state |
| `Documentation/INFERRED_PRICE_LOGIC.md` | §2.5 rewritten as REMOVED; §2b and §4.C |
| `Documentation/System_Architecture.md` | Stage 1.5 |
| `Documentation/System_State.md` | new section |
| `Documentation/Business_Documents/Agent_Arbitrage_Product_Overview.md` | customer-facing AI-rescue claim removed |
| `diagnose_inferred_sales.py` | prose only; `MirrorsProduction` green |

**PR #342 follow-up (`701e888`) — stale references review found:**

| file | change |
| :--- | :--- |
| `Documentation/Business_Documents/Agent_Arbitrage_Product_Overview.md` | competitor list: "(d) AI rescue ... all four" → three |
| `Documentation/Dashboard_Specification.md`, `Documentation/System_Architecture.md` | `Deal Trust` `'-'` described correctly |
| `keepa_deals/stable_calculations.py` | live comment above `inferred_sale_count` |
| `tests/test_cleanup_low_est_rows.py`, `tests/test_field_mappings_call_contract.py` | comments only; the `XAI_TOKEN` patch kept, since the AI Reasonableness Check still reads it |

**PR #343 (merged) — the diagnostic's conclusion:**

| file | change |
| :--- | :--- |
| `diagnose_inferred_sales.py` | `reconstruct_prefix_value` + `_print_prefix_reconstruction`; `recompute` rewritten; `confirm_sales` returns a 3-tuple; conclusion rule in the module docstring |
| `tests/test_diagnose_inferred_sales.py` | `PreFixReconstruction`, 8 tests; helper follows the new arity |
| `Documentation/INFERRED_PRICE_LOGIC.md` | what the script reports |
