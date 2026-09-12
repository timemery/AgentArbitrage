# Dev Log Entry: Take the Inferred Sale Price From Before the Offer Drop, and Why the Tolerance Was Wrong

**STATUS BLOCK**
- **Shipped:** PR #340 — price association now takes the last price point **strictly before** the offer drop (`direction='backward'`, `allow_exact_matches=False`), a `pd.isna` guard, the `diagnose_inferred_sales.py` mirror re-synced, 3 docs updated, 13 new tests.
- **Live:** merged `4166e03`. Box fast-forwarded `0b9dc78 → 4166e03` (spanning PR #339's docs-only dev log), `deploy_update.sh` clean. Recharge Mode set 16:50:59 UTC, 60-minute timeout, so first post-fix deals land after ~17:51 UTC.
- **The tolerance in the brief was wrong, and it was Tim's to approve — which is what caught it.** I proposed 240h from fixtures; 14 tokens of real Keepa history refuted it. Removed before merge. See §2(a).
- **Measured:** real preceding-gaps 3.0, 5.1, 10.2, 252.1, 389.6, 516.4, 2281.4h across 7 sales / 3 ASINs. Bimodal, nothing between 10h and 252h, median 252.1h. A 240h threshold would have discarded **4 of 7 true sales**.
- **`allow_exact_matches=False` is carrying the fix**, not the direction alone: 4 of those 7 sales had a price point on the **exact minute** of the offer drop.
- **Correction to `2026-09-11b`:** its "gap 60.3 days" was distance to the **nearest** point, not the age of the preceding one. Do not read that figure as evidence for a threshold. §2(c).
- **User-visible:** nothing today. Heavy path only, **no existing row is repaired**, and the fix **cannot be confirmed same-day** — verification is new deals accruing against the pre-deploy baseline over days. Suite 135 → 148 passed, 0 failed.
- **Next:** recovery plan for rows already carrying inflated prices. Then the 240-hour rank-confirmation window and the IQR at `n <= 3`.

**Date:** September 12, 2026
**Files:** see §9
**Status:** SUCCESS — MERGED TO MAIN (PR #340). This entry is the docs-only follow-up.

---

## 1. Task Overview

Open item 1 from `Dev_Logs/2026-09-12_Trustworthy_Test_Suite_And_Last_Update_Retry.md` §7, price-association half only, unblocked by the test-suite work earlier the same day.

The defect was already diagnosed in `2026-09-11b` §4b against live data, so the job was to fix it, not to re-derive it. Scope was explicitly fenced and held: the 240-hour rank-confirmation window, the IQR and its behaviour at `n <= 3`, the XAI rescue path, any minimum sale count or UI change, the Amazon ceiling clamp, and repair of existing rows were all listed as out of bounds and none were touched.

Three rounds. Round 1 shipped the fix with a 240-hour tolerance and asked for approval of that value. Tim withheld approval and asked for the measurement on real data instead. Round 2 established that the sandbox cannot make that measurement, and produced a validated command for the box. Round 3 removed the tolerance on the result.

The tolerance being an owner decision is the only reason the wrong number did not ship. Worth recording plainly: my justification for it read as reasonable and was built on a measurement of the wrong thing.

---

## 2. Premises That Turned Out Wrong

**(a) "Add a time tolerance so a drop with no nearby prior price point yields no price rather than a distant one."** — the brief, and I agreed with it and implemented it. **Wrong.** The brief also said not to pick the value blind and that the value was Tim's to approve, which is what stopped it.

Measured on live Keepa history for the three ASINs of the 09-11 diagnostic (14 tokens), the gap between an offer drop and the price point immediately **preceding** it, across all 7 confirmed sales:

| | hours |
| :--- | :--- |
| gaps | 3.0, 5.1, 10.2, 252.1, 389.6, 516.4, 2281.4 |
| median | 252.1 |
| max | 2281.4 (95.1 days) |
| drops with no prior point | **0 of 7** |

Bimodal, with **nothing at all between 10h and 252h**. A 240-hour threshold lands in that void and cuts the distribution at its median: **4 of 7 real sales discarded**. The constant, its `tolerance=` argument and the three boundary tests that pinned it were removed before merge.

**(b) "The fixtures can justify the tolerance."** — mine, in the round-1 PR body. The fixture measurement was: 1h (×17), 6h (×15), 24h (×2), 240h (×1). Every one of those numbers is **the fixture generator's grid step**, not a property of Keepa data:

| fixture | grid |
| :--- | :--- |
| `tests/test_1yr_avg_logic.py:37` | hourly |
| `tests/test_1yr_avg_no_fallback.py:91,95` | `step_hours = 24 // points_per_day`, so hourly or 6-hourly |
| `tests/test_diagnose_inferred_sales.py:52,55` | 6-hourly |
| `tests/test_synchronous_updates.py:30,77` | two points, `base_time + 1440` — the 24h pair |
| `tests/test_xai_sales_inference.py:39` | one price point, drop at day 10 — and never run through `infer_sale_events` |

So the table established a floor of 24 hours and **no ceiling whatsoever**, and I said so in the PR body. What I did not draw the obvious conclusion from is that a distribution made entirely of generator step sizes cannot support *any* value above the floor. **Do not measure a data-shape question against synthetic fixtures.** The pre-existing suite had no sparse-history fixture at all, which is exactly why it could not see this.

**(c) "The nearest price point was 60.3 days from the drop."** — `2026-09-11b` §4b, mine, and carried forward into this brief as the motivating evidence for a tolerance. **True as printed, but not the quantity it was read as.** On the pre-fix diagnostic (`afa8b6a:diagnose_inferred_sales.py:279-280`), `gap_days` was computed from `price_df.loc[deltas.idxmin()]` — the distance to the point `merge_asof(direction='nearest')` chose, which is the **at-or-after** point in a step-up. It is not the age of the preceding point, and the two differ by the whole width of the gap. In a local fixture whose preceding point was 6.0 hours old, that column reported **0.0**.

Fixed by renaming the column to **`PRECEDING-GAP`** and by `INFERRED_PRICE_LOGIC.md` §2b.1, which records the correction. **Do not read the 60.3-day figure in `2026-09-11b` as the age of a preceding price point.**

**(d) "`git show main:diagnose_inferred_sales.py`."** — mine, in the round-2 command. It failed: `path 'diagnose_inferred_sales.py' exists on disk, but not in 'main'`. The sandbox's local `main` was stale at `203f83c`, which predates the file. `origin/main` was `afa8b6a`. See §8.

---

## 3. Hypotheses Raised and Discarded

**3.1 "Pick a tolerance in the 24h–60d range that the fixtures allow."** REJECTED by measurement (§2(a)). Recorded because the range looked narrow when expressed as "ten times the floor" and is in fact more than 60× wide, and the real distribution is bimodal across it. Any value in that range is a coin toss dressed as a derivation.

**3.2 "Read the tolerance from the 240-hour rank-confirmation window."** REJECTED in round 1, before the data arrived, and the reasoning still holds independently: the confirmation window answers "is this rank drop the same event as this offer drop" and a price tolerance would answer "is this price point still in force". Two different judgements; coupling them means a future change to one silently moves the other. The 240 magnitude coincidence made this tempting, which is precisely why it is written down as refused.

**3.3 "Lowering the tolerance only errs safe, because it produces NULLs rather than wrong prices."** REJECTED. The argument is true in isolation and wrong in context. AGENTS.md §7.1 requires erring toward rejection over a wrong price, so this felt aligned — but the rows it rejects are **slow-moving inventory whose price has not changed**, which is the Silver Standard candidate the peek filter was deliberately loosened to catch (`salesRankDrops365` threshold lowered to 1). "Errs safe" is not a licence to discard the target population.

**3.4 "Run the diagnostic from the sandbox to get the real numbers."** IMPOSSIBLE, not merely rejected, and established by test rather than assumed. Two independent blockers, both in §8. Recorded because the instinct is to try and then report a vague failure; the useful output is which of the two blockers applies.

**3.5 "Check out the branch on the box to run the branch's diagnostic."** REJECTED. The box runs from its working tree, so a checkout there **is** a deployment. Superseded by 3.6.

**3.6 "Write the branch's diagnostic to the box under a second filename and run that."** REJECTED once the deployed file was actually read: `afa8b6a:diagnose_inferred_sales.py:316` already stores `price_before_timestamp` on every confirmed sale, so the preceding age is `event_timestamp - price_before_timestamp` and the **deployed** script can answer the question with nothing written to the box at all. The measurement command was then dry-run against a byte-identical copy of `origin/main`'s file, with `fetch` stubbed, before it was handed over — so a formatting bug could not waste the 18-token budget. It came in at 14.

**3.7 "Remove the `pd.isna` guard along with the tolerance."** REJECTED, and this one would have been a live defect. A backward match still returns `NaN` whenever a drop precedes **every** point in its series, independently of any threshold, and `NaN <= 0` is `False`, so the pre-existing `price <= 0` check at `stable_calculations.py:365` cannot catch it. A `NaN` reaching `confirmed_sales` poisons the IQR bounds, the mean and the mode for the whole ASIN. The guard is now the *only* way a confirmed drop loses its price.

---

## 4. Root Cause

`csv[1]` and `csv[2]` hold the **lowest** New / Used offer price, not the price of any particular copy. When the cheapest copy sells, the series does not record what it sold for — it steps **up** to whatever the next cheapest listing asks, at essentially the same timestamp as the offer-count drop that marks the sale.

`merge_asof(direction='nearest')` has no tie-break, so on a drop whose neighbouring price points straddle it, it could land on the at-or-after point and store the asking price of a copy that did **not** sell. Because Keepa stamps the offer-count drop and the price step-up at the **same minute**, that was not an edge case: the at-or-after point sat at distance zero and won outright. Confirmed live on 5 of 7 sales across 3 ASINs (`2026-09-11b` §4b): $124.85 recorded as $1,000.00, $49.95 as $499.95, $328.19 as $625.59. The round numbers are the tell — those are prices a seller typed into a listing.

**And a second root cause, of the wrong fix rather than the defect: gap length is not a measure of staleness.** The price series is a **change-log** — a point exists only when the value changes. A months-old point therefore means the lowest offer **had not changed**, which makes the distant point the **correct** answer. Gap length cannot distinguish that from a genuine tracking hole, because both look like an absence of points. A continuity check could: evidence that the series was live across the gap and the value genuinely held. That is the right instrument and it was **not built** (§7).

---

## 5. The Fix

Two arguments and one guard, in `infer_sale_events`:

```python
price_at_sale_time = pd.merge_asof(
    pd.DataFrame([drop]), price_df_to_use, on='timestamp',
    direction='backward', allow_exact_matches=False,
)['price_cents'].iloc[0]
```

`direction='backward'` takes the last point before the drop, at any distance. `allow_exact_matches=False` excludes the same-minute point, and the measurement showed it doing most of the work — 4 of the 7 live sales had a price point on the exact minute of the drop. The `pd.isna` guard precedes the existing `price <= 0` check (§3.7). A drop whose price cannot be associated **still counts** in the `Deal Trust` denominator.

The module now carries the seven measured gaps and the change-log reasoning where the rejected constant used to sit, so the next reader sees the evidence and not just the conclusion.

**Measured, before and after:**

| | parent `afa8b6a` | merged `4166e03` |
| :--- | :--- | :--- |
| suite | 135 passed / 0 failed | **148 passed / 0 failed** |
| step-up fixture records | $499.95 (asking price) | **$28.99 (sale price)** |
| new tests failing on parent | — | **10 of the round-1 set** |
| real gaps that lose their price | — | **0 of 7** |

`tests/test_price_association.py` is 13 tests and 11 subtests. Its fixtures are deliberately **sparse** — two or three points per series at exact offsets from the drop — because a dense grid cannot express "the only prior price point is 95 days old", which is the shape the fixture-derived tolerance was blind to. `DistantPrecedingPointsStillAssociate` drives all 7 measured gaps as an executable fact and asserts that exactly 4 exceed 240h, so the cost of re-adding a threshold stays visible. `NoTimeThreshold` pins the **absence**: constant gone, no `tolerance=` in source, reasoning and the widest gap present — the same pattern as `tests/test_field_mappings_call_contract.py`'s pinning of `FUNCTION_LIST[10] = None`, because "add a bound" is an intuition already tried and refuted.

`diagnose_inferred_sales.py` re-implements the correlation loop rather than calling it (it must not spend xAI budget), so the mirror was re-synced and `MirrorsProduction` kept green. Its PRICE STEP-UP TEST section was **repurposed, not removed**: it now reports what today's code records alongside what the pre-fix nearest-match would have stored, which is what lets a stored number on a pre-fix row still be accounted for.

---

## 6. Deployment Result

PR #340 merged as **`4166e03`**. Repo main advanced `afa8b6a → 4166e03`; the box's working copy **fast-forwarded `0b9dc78 → 4166e03`**, spanning PR #339 as well (docs-only, 199 lines of dev log, nothing the box needed earlier). `0b9dc78` is an ancestor of `4166e03`, verified, so the pull was a clean fast-forward with no merge. `deploy_update.sh` clean.

**Recharge Mode set 2026-09-12 16:50:59 UTC with a 60-minute timeout**, which `deploy_update.sh` forces via `Diagnostics/force_pause.py` because the stop step wipes the Redis holding the token bucket. First post-fix deals therefore land after roughly **17:51 UTC**.

**Pre-deploy baseline**, for comparison over the coming days:

| metric | value |
| :--- | :--- |
| priced rows | 2,598 |
| rows with `Inferred_Sale_Count` | 129 |
| average `List_at` | $126.10 |
| newest row | 16:45:14 UTC |

**This is heavy-path only, no existing row is repaired, and the fix cannot be confirmed same-day.** `_process_lightweight_update` does not run the inference, and `recalculator.py` is API-free and cannot rebuild `List_at` or `1yr_Avg` — it derives from `infer_sale_events`, which consumes Keepa `csv` history that `deals.db` never stores. Only **newly discovered** deals carry the corrected association. Every row written before the merge keeps its inflated value.

So there is no same-day signal, and claiming one would be false. The honest verification is **new deals accumulating against that baseline over days**: no new row carrying a suspiciously round `List_at` ($150.00, $200.00, $250.00, $499.95, $1,000.00), `Inferred_Sale_Count` and `Deal_Trust` broadly unchanged rather than falling, and a low or zero count of `"price point exists before it"` in `celery_worker.log` (it fires only when a drop precedes every point in its series, which was 0 of 7 live). A spot-check of one new deal against `diagnose_inferred_sales.py` should show `recorded` reading `before` on every row; the same check against an old row (e.g. `1890919489 --stored-price 1000.00`) should show the stored value matching `old would`, which is the confirmation that existing rows are unrepaired and is the input to the recovery decision.

---

## 7. Open Items

Priority order, owner-set, carried from `2026-09-12` §7 with one addition.

**1. A recovery plan for rows already carrying inflated prices.** Now the top item, and the one that decides when the dashboard is trustworthy again. The association fix repairs **nothing**: 2,598 priced rows at the merge were all written under the old logic. Re-fetch versus delete has to be decided; `diagnose_inferred_sales.py`'s `old would` column identifies an affected row at 6 tokens each.

**2. The 240-hour rank-confirmation window accepts unrelated rank drops.** `2026-09-11b` §4b names it as a distinct defect: the $699 row's two highest "sales" are listing removals that coincided with an unrelated rank drop inside the window. Untouched here, explicitly out of scope.

**3. The IQR gives no protection at `n <= 3`** and trimmed the one *plausible* low sale ($85.39) on `1429097078` because the inflated ones dominated the quartiles. Untouched here.

**4. A continuity-based stale-price guard. NEW, from this session.** The correct instrument for the question the tolerance was trying to answer (§4). It needs evidence that the price series was live across the gap and the value genuinely held, not gap length. Not built, and not worth building until something demonstrates a real tracking hole — the live sample had 0 drops with no prior point.

**5. Carried forward.** Amazon ceiling clamp and the A-10 AI-check bypass. Blank **Ago** on 893 visible rows. Expiry policy for permanently incomplete rows. The swallowed exceptions in `get_trend` and `analyze_sales_rank_trends`. `POST /api/run-janitor` auth. Fee and settings defaults. `backup_db.sh` copying a WAL database with `cp`. `last_price_change` typed `REAL` while storing a timestamp string. `AGENTS.md` §5.2's `DATABASE_URL` needing to be a shell-level env var.

---

## 8. Infrastructure Findings

Facts established by test or by reading source this session, written down nowhere else in the repo.

**A Claude Code sandbox session cannot run any Keepa diagnostic. Two independent blockers, both confirmed rather than assumed.** First, no credential exists: there is no `.env` in the working copy, `KEEPA_API_KEY` is unset in the environment, and it is not recoverable from the database either — `user_credentials` has 0 rows and only the columns `user_id`, `refresh_token`, `updated_at`, so it never held a Keepa key. Second, the host is blocked: `curl https://api.keepa.com/token` returns `curl: (56) CONNECT tunnel failed, response 403`, and the agent proxy's own status endpoint reports it as `{"kind": "connect_rejected", "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)", "host": "api.keepa.com:443"}`. **Any task needing live Keepa data must be run on the box.** Recorded because the failure mode is silent-looking: `fetch_product_batch` would surface this as a generic fetch failure, not as a policy denial.

**The sandbox's local `main` branch is stale and can predate files that exist on the real main.** It sat at `203f83c` while `origin/main` was `afa8b6a`, so `git show main:diagnose_inferred_sales.py` failed with `path ... exists on disk, but not in 'main'`. **Reason about what the box runs from `origin/main` after an explicit `git fetch origin main`, never from `main`.** The remote-tracking ref is also stale until fetched: `origin/claude/wizardly-edison-ovhbj5` resolved to a commit before the branch existed on the remote at all.

**`gap_days` in the pre-fix diagnostic was the nearest-match distance, not the preceding age.** `afa8b6a:diagnose_inferred_sales.py:279-280` computes it from `price_df.loc[deltas.idxmin()]`. This is the source of premise (c) and the reason a step-up sale could report a gap of `0.0` while its preceding point was hours old.

**The same pre-fix diagnostic already stored everything needed to measure the preceding age.** `afa8b6a:diagnose_inferred_sales.py:316` sets `price_before_timestamp` on every confirmed sale, and `confirm_sales(offer_drops, csv_data, window_start)` returns a 2-tuple of `(confirmed, rejected)`. That is what made the box measurement possible with **nothing written to the box** — no checkout, no file, no restart.

**`MIN_SALES_FOR_ANALYSIS` is a function-local, not a module-level constant.** `keepa_deals/stable_calculations.py:479`, inside `analyze_sales_performance` (def at `:464`). `diagnose_inferred_sales.py:114` mirrors it with the comment `# stable_calculations.py: MIN_SALES_FOR_ANALYSIS`, which reads as a module-level reference. Cosmetic — the values agree — but the comment is misleading and an import of that name would fail.

**Before this PR the suite had no sparse Keepa history fixture.** All five modules that build a `csv` history use uniform grids (§2(b) table). A question about the *shape* of Keepa data therefore could not be answered from `tests/` at all, and appeared to be answerable, which is the trap in §2(b).

---

## 9. Files Modified

**PR #340 (merged) — round 1, the association fix:**

| file | change |
| :--- | :--- |
| `keepa_deals/stable_calculations.py` | `infer_sale_events`: `direction='backward'`, `allow_exact_matches=False`, `pd.isna` guard |
| `diagnose_inferred_sales.py` | mirror re-synced; `gap (d)` → `PRECEDING-GAP`; step-up section repurposed to report what the pre-fix nearest-match would have stored |
| `tests/test_price_association.py` | new |
| `tests/test_diagnose_inferred_sales.py` | step-up expectation inverted; `chose_at_or_after` → `legacy_chose_at_or_after` |
| `Documentation/INFERRED_PRICE_LOGIC.md` | §2b rewritten; new §2b.1; fifth hard-won lesson |
| `Documentation/Data_Logic.md` | Price Association bullets under "Inferred Sales (The Engine)" |
| `Documentation/System_State.md` | September 2026 entry |

**PR #340 — round 3 (the tolerance removal, on the box measurement):**

| file | change |
| :--- | :--- |
| `keepa_deals/stable_calculations.py` | `PRICE_ASSOCIATION_TOLERANCE_HOURS` and `tolerance=` removed; the seven measured gaps and the change-log reasoning recorded in their place |
| `diagnose_inferred_sales.py` | tolerance dropped from the mirror and the import; rejection reason reduced to the no-prior-point case; `PRECEDING-GAP` explanation rewritten |
| `tests/test_price_association.py` | boundary tests and `TheConstant` replaced by `DistantPrecedingPointsStillAssociate`, `NoPriorPointYieldsNoPrice` and `NoTimeThreshold` |
| `Documentation/INFERRED_PRICE_LOGIC.md` | §2b.1 rewritten to "There is deliberately NO time threshold", with the measurement, the premise-(c) correction and the continuity open item |
| `Documentation/Data_Logic.md` | no-threshold bullets |
| `Documentation/System_State.md` | no-threshold paragraph |

Diffstat, `afa8b6a..4166e03`: 7 files, 653 insertions, 102 deletions.

**This PR:**

| file | change |
| :--- | :--- |
| `Dev_Logs/2026-09-12b_Fix_Price_Association_In_Infer_Sale_Events.md` | this entry |
