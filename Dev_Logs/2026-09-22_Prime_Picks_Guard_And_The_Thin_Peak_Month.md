# Dev Log Entry: The Sweep Closed, and What It Uncovered Underneath

**STATUS BLOCK**
- **The pricing repair sweep is FINISHED.** Ended 2026-09-21 19:36 UTC: **4,000 attempted, 3,769 repaired, 231 skipped, 232 stale rows remaining.** Trello #139's long-running work is done.
- **`max_xai_calls_per_day` reverted 5000 → 1000 on the box and deployed.** The revert needed a deploy, not just an edit: workers read the value once at start (audit A-31). The committed docs, which always described 1000, are now true of the box again.
- **Shipped:** PR **#352** — Prime Picks never shows a deal whose pricing was not repaired, three guards on one shared predicate. PR **#353** — `audit_list_at_sources.py`, read-only Phase 1 measurement. Both merged and live.
- **PR #353 was corrected mid-build, by the owner, on a premise I had wrong:** a New-price cap must not use TODAY's price. The product buys at the trough and sells at the peak, so the current price is the **buy** side. §2.
- **THE HEADLINE IS NOT THE ONE WE WENT LOOKING FOR.** The duplicate-price-point mechanism is real and small. The main source of inflation is that the peak month is chosen by `idxmax` over up to twelve **very thin** monthly medians: **41 of 43 median-set rows have a peak month of ≤ 3 sales, median 1**, and on **31 of 50 rows the peak rests on a single price point**. For a slow book, `List at` is effectively **the highest single sale in three years**. §5.
- **Five decisions taken, none implemented.** Pool the peak season across years; do not recommend books too thin even when pooled (persist unpriced, never delete); pick the minimum sale count from measured removals; gate or drop the Amazon ceiling's CURRENT reading, shipped only paired with the cap; one `PRICING_LOGIC_VERSION` 2 → 3 bump for all of it. §6.
- **Re-sweep cost for that bump: ~8 days** at the reverted 1000 xAI calls/day. §6(e).
- **STATUS: MEASURED AND DECIDED, NOT BUILT.** Phase 2 is a fresh session. No pricing logic changed today.

**Date:** September 22, 2026
**Files:** see §9
**Status:** SHIPPED — two PRs merged (#352, #353); the pricing fix they exist to inform is not written.

---

## 1. Task Overview

Three pieces of work, in the order the day forced them.

| # | what | outcome |
| :--- | :--- | :--- |
| 1 | Close out the pricing repair sweep (Trello #139) | done; 232 stale rows remain, all in the skip backlog's shadow |
| 2 | PR #352 — stop Prime Picks recommending an unrepaired row | merged, deployed |
| 3 | PR #353 — measure where `List at` actually comes from | merged, deployed, run on the box |

Item 2 came out of item 1: the sweep finished, and the very next Prime Picks rebuild put an
unrepaired row on screen anyway. Item 3 came out of item 2: having stopped showing rows the
sweep had *not* fixed, the obvious next question was whether the rows it *had* fixed were
right. They mostly are not, for a reason nobody had named.

### The sweep, closed

Ended **2026-09-21 19:36 UTC**.

| | |
| :--- | :--- |
| attempted | 4,000 |
| repaired | 3,769 |
| skipped | 231 |
| stale remaining | 232 |

`max_xai_calls_per_day` was reverted **5000 → 1000** and deployed. That is item §7.3 of both the
2026-09-19 and 2026-09-20 entries, carried forward twice and now closed. **The revert needed a
deploy, not just a file edit** — workers read the value once at process start (audit A-31), so an
edited `settings.json` with no restart would have left the 5000 in force in every running worker.
The committed documentation always described the 1000 default and was never wrong; the box has
now caught up to it.

---

## 2. Premises That Turned Out Wrong

**(a) "A cap on `List at` should use the lowest current New offer."** — mine, in the first draft of
PR #353. **Wrong, and corrected by the owner before merge.**

The product buys at the trough and sells at the peak. Today's New offer is therefore the **buy**
side: it bounds what an arbitrageur pays for a copy now, not what that copy can be listed at when
its season comes round months later. Capping a peak-season list price with an off-season market
price compares two different points in the same cycle, and would have clipped exactly the
seasonal premium the business model exists to capture.

The corrected measure is the lowest New offer **during the peak-season window(s) that fed
`List at`** — the calendar months holding the sales the pricing code actually used. Today's figure
is still reported, on two bases and explicitly labelled a comparison. Pinned by
`TheOverstatementUsesThePeakWindowNotToday`: a $5.00 price today must not shrink a $375.66
peak-season overstatement, and a row with no New price in its peak window must report **no**
overstatement rather than falling back to today's.

The lesson is not "check with the owner". It is that a bound and the thing it bounds have to be
measured at the same point in a seasonal cycle, and nothing in the code or docs said so, because
until this week nothing compared `List at` to a market price at all.

**(b) "`prime_picks` is not beat-scheduled, so it will not self-heal."** — `System_State.md` line 77,
pre-existing, and it contradicted `System_Architecture.md` §3.D. **§3.D was right.**
`generate_prime_picks` is chained after `clean_stale_deals`, which Beat runs on
`crontab(minute=0, hour='*/4')`. Confirmed on the box: a rebuild at **12:00:21 UTC** on 2026-09-22
with no manual refresh, landing in the Janitor's slot. Corrected in place.

**(c) "The duplicate price point is the reason `List at` is inflated."** — the working hypothesis the
whole audit was built to test. **Confirmed as a real mechanism and demoted as an explanation.**
It is 4 rows in 50. §5 has what actually does it.

---

## 3. Hypotheses Raised and Discarded

- **"Pick #4 was a stale-pricing row the sweep missed."** Half right — ASIN `1418548839` carried
  `Pricing_Logic_Version` NULL, but the sweep had not missed it. It had **attempted and skipped**
  it, recorded in the skip manifest as *"heavy processing returned nothing (usually: no used
  offer)"*. A skipped row keeps its old prices indefinitely (2026-09-17 §7.7), so it stays
  eligible for selection forever. Discarding "the sweep missed it" is what turned a one-row
  curiosity into a structural guard.
- **"`1600910513` is inflated because two sales shared one price point."** The audit confirmed the
  shape — `mode-shared`, two drops matched to one change-log point — and then showed that
  **de-duplicating does not change its `List at` at all**. Its peak month held only that one point:
  removing one of two identical sales leaves a median of one number, which is the same number.
  The duplicate was a symptom of the thinness, not the cause of the price.
- **"Two sales at the same price are the artifact."** Discarded in the design, by requiring the
  matched point's own timestamp rather than price equality. Two genuinely separate points that
  happen to hold the same price are ordinary repricing. The live run found both kinds.

---

## 4. Root Cause (of the thing we set out to find)

`analyze_sales_performance` breaks the `List at` tie by **frequency**: `st.mode` of the peak
month's sale prices, falling back to the median only when no value occurs twice. The price
association (PR #340) takes the last change-log point strictly before an offer drop **at any
distance**, which is correct — `csv[1]`/`csv[2]` are change-logs, so a months-old point means the
price had not changed. But it means two offer drops with no price change between them receive the
**same point**, and therefore the identical price.

In a peak month where every other price is distinct, that pair is the only repeated value and wins
the frequency vote uncontested. One asking price, counted twice, becomes `List at`.

**Measured: 4 of 50 rows.** Real, reproducible, and not where the money is.

---

## 5. THE HEADLINE FINDING — the peak month is an order statistic over almost no data

This was not what the audit was built to find. It fell out of the results.

`peak_month = monthly_stats['median'].idxmax()` — the calendar month with the highest median sale
price wins, out of up to twelve. `List at` is then the mode or median **within** that month. So
`List at` is approximately *"the highest monthly median"*: a **maximum over a set of estimates**,
which is upward-biased whenever those estimates are noisy. How noisy depends entirely on how many
sales sit behind each month.

Measured on the 50-row sample:

| | |
| :--- | :--- |
| median-set rows | 43 of 50 |
| ...whose peak month holds ≤ 3 sales | **41 of 43** |
| median peak-month sale count | **1** |
| rows whose peak rests on a **single price point** | **31 of 50** |
| worst-10 rows by overstatement that are median-set | **8 of 10** |

**The median peak month contains one sale.** The "median of the peak month's prices" is then the
median of a single number — that number. The month was selected *because* that number was the
highest. For a slow-moving book, `List at` is therefore **the highest single inferred sale in three
years**, dressed as a seasonal average.

That explains the worst-10 list far better than the mode does: eight of the ten are median-set, so
no duplicate is involved in them at all. It also explains why `1600910513` does not improve when
de-duplicated — its peak month has one price point, and one price point is one price however many
sales point at it.

**Why this is not simply "the prices are wrong."** The inferred sale prices may each be perfectly
correct. The defect is in the **estimator**: taking a maximum over twelve thin samples and
presenting the winner as a seasonal price. The buy-trough/sell-peak thesis is sound and the
seasonal premium is real; what is not sound is estimating the peak from one observation.

**Why it hid for so long.** Every previous investigation asked whether a *price* was right —
the Keepa Stats Fallback, the `avg365` tier fallback, the xAI Sales Rescue, the price
association. All four were about the provenance of an individual number, and all four were real.
None of them asked whether the *selection rule over correct numbers* was sound. The audit could
only see it because it recorded, per row, how many sales and how many distinct price points the
winning month actually rested on.

---

## 6. Decisions Taken — none implemented

Owner decisions, made on the measured evidence, to be built in a separate session.

**(a) Pool the peak season's months across years.** Do **not** require ≥ 2 sales in one calendar
month of one year — require them in the peak *season*, pooling the same month (or month-window)
across the three-year history. Requiring two sales in a single calendar month would delete the
seasonal signal for exactly the slow inventory the system is built to find; pooling keeps the
premium while giving the estimate more than one observation to stand on.

**(b) A book too thin even when pooled must not be recommended at all.** It is **persisted
unpriced** — `List_at` NULL — so the dashboard's data-completeness filter hides it. It is **never
deleted**: deleting re-creates the re-acquisition loop AGENTS.md §7.8 exists to prevent, and the
row costs nothing while it sits. This is the same asymmetry `pricing_version.py` already states —
a missing price hides a deal, and hiding a deal on a guess is the cheaper error only when the
alternative is recommending a number we know is unsupported.

**(c) The minimum sale count — 2, 3 or 4 — is to be chosen from measured removals**, not picked.
The decision needs, for each candidate threshold, how many currently-visible rows it removes. That
measurement does not exist yet.

**(d) The Amazon ceiling's CURRENT reading: drop it, or gate it on `today's month == peak month`.**
Both trailing averages stay — they are the only Amazon-based rail for books Amazon stocks
intermittently, and they clip downward, which is the safe direction. Measured effect is small: the
ceiling clipped 4 rows, of which **1** was on today's price taken outside the peak month and 3 on a
blended trailing average. **It ships only paired with the cap**, because removing a clamp can only
*raise* prices, and shipping that alone would be a price increase dressed as a correctness fix.

**(e) One `PRICING_LOGIC_VERSION` 2 → 3 bump covers all of it**, so the re-sweep is paid once.
At the reverted 1000 xAI calls/day and ~1.7 calls per row, that is **~8 days** for ~4,500 rows.
Two consequences to plan around, both known:

- **Agent's Choice empties the moment the bump deploys** and refills as the sweep progresses.
  That is PR #352's read-time guard working correctly, but it is visible to subscribers.
- **The 231-row skip backlog sorts back to the top** of the new run (§7.1, still open), re-paying
  ~7 Keepa tokens each before any new work is reached.

---

## 7. What Was Built Today

### PR #352 — stale pricing is never a Prime Pick

**Found by:** Prime Picks rebuilt 2026-09-22 12:00 UTC with four picks. Pick **#4** was ASIN
`1418548839` — `List_at` 219.66, `Pricing_Logic_Version` **NULL**. The sweep's skip manifest listed
it as *"heavy processing returned nothing (usually: no used offer)"*, so its price came from the
pre-2026-09-12 logic the sweep existed to replace. 231 rows were skipped in that run, so this
recurs by construction.

**The invariant:** no row with stale pricing is ever shown as a Prime Pick, on any path.

Filtering Pass 1 alone does not hold it, because **two paths through `generate_prime_picks` return
without writing to `prime_picks` at all, by design** (the Graceful Fallback, AGENTS.md §7.10): Pass 1
finding no eligible candidates, and Pass 2 failing or selecting nothing. A pick chosen before the
filter existed survives every one of those runs. Three guards, one shared predicate:

| where | governs | why it is needed |
| :--- | :--- | :--- |
| Pass 1 SQL | what may **enter** the cache | the selection itself |
| `prune_stale_priced_picks`, before Pass 1 on **every** invocation | what may **stay** in it | the two paths above preserve the cache untouched |
| the Agent's Choice branch of `/api/deals` | what may be **shown** from it | the cache is up to 4 hours old, and a version bump re-stales the whole table at deploy |

`CURRENT_PRICING_PREDICATE` is **derived** in `keepa_deals/pricing_version.py` as
`'NOT ' + STALE_PRICING_PREDICATE`, not restated, so the display rule and `repair_pricing.py`'s
scheduling rule cannot drift. A test fails the build if any consumer hand-rolls the comparison.

The eviction **narrows** the Graceful Fallback rather than removing it: a preserved run keeps its
current-priced picks and loses only the stale ones. If that empties the cache, Agent's Choice shows
nothing — correct, because the alternative is recommending a price the system knows is superseded.
**Agent's Choice only**; the main grid still shows stale-priced rows, because filtering it would
have emptied the dashboard while the sweep was still running.

Deployed with `deploy_update.sh` (it touches `wsgi_handler.py` and a Celery task module).

### PR #353 — `audit_list_at_sources.py`, read-only

Built because `diagnose_inferred_sales.py` explains one ASIN's sale events and then stops exactly
where the question starts, in its own words: *"List at = normal branch (peak-month mode/median). Not
recomputed here; this diagnostic does not classify seasons."*

**It measures production rather than a copy of it.** `infer_sale_events` and
`analyze_sales_performance` are called directly, so the peak-month choice, the mode/median branch,
the IQR and both ceilings are production's. Two interventions, both recorded in the output:

1. `pd.merge_asof` is wrapped inside `stable_calculations` for the duration of one call, so the
   matched point's own timestamp survives the merge. **pandas still does the matching**; the wrapper
   adds a passthrough column and reads which row won. That is what makes sale-to-point identity
   exact — two separate points holding the same price are never conflated.
2. `_query_xai_for_reasonableness` is stubbed to `True`, so the run spends no quota and is
   deterministic. Each row records whether that check is live in production.

**The one mirror** is the Amazon ceiling — four lines of arithmetic inline mid-function with no seam
to instrument. It is made safe by being **checked**: whenever the mirror says a price was clipped,
the row records whether production's own output equals the ceiling, and the summary counts any
disagreement. A wrong mirror surfaces as a disagreement rather than a confident wrong number.

Read-only URI (`mode=ro`), `TokenManager` in batches of 5, `--limit` 50 by default with an unbounded
run **refused**, Keepa's own `tokensConsumed` printed. ≤25 lines to stdout and nothing else;
per-row detail to `Diagnostics/`, with the `git add -f` printed.

Deployed by `git pull` alone — nothing imports it, exactly as for `repair_pricing.py` (2026-09-19 §8).

### Phase 1 results — 50 visible rows by `List_at` DESC, ~350 tokens

A **worst-case sample, not a representative one**: the fifty highest-priced visible rows.

| | |
| :--- | :--- |
| mode backed by ONE SHARED price point | **4** — reconstruction agreed with production on all 4, ceiling overwrote none |
| de-duplicating changes `List at` on | **6 rows**, median drop **$20.56** |
| rows with a New price in a peak window | **33 of 50** |
| `List at` above the peak-window **min** floor | **17**, median $146.66, total $2,800.61 |
| under the proposed rule (median-of-windows + $3.99) | **15 of 50 capped**, median **$155.82**, total **$2,680.12** |
| rows with **no** New price in the peak window | **17** — uncappable by any peak-window rule |
| Amazon ceiling clipped a peak-season price | **4** — 1 on today's price outside the peak month, 3 on a blended trailing average |
| worst-10 rows that are median-set | **8 of 10** |

**Six rows changed on de-duplication but only four were `mode-shared`.** `dedupe_by_source_point`
collapses shared points across the *whole* sale list, so removing a duplicate in a **non-peak** month
can move that month's median and change which month wins. The duplicate effect is not confined to
the rows the classifier flags.

**Single-row run on `1600910513`:** `mode-shared`, and de-duplicating does **not** change its price —
its peak month held only that one $375.66 point. No New price existed in its peak window either, so
neither proposed fix touches it. Only the thin-peak rule of §5/§6(a) would.

The proposed-rule figures came from a **post-hoc one-liner run on the box against the detail file**,
not from a second Keepa run: stdlib only, read-only, zero tokens. That is the pattern to reuse —
the audit writes enough per-row detail that re-scoring a different rule costs nothing.

---

## 8. Infrastructure Findings

**The audit cannot reconstruct the winning versus second-highest monthly median.** It records the
winning month's *name* and the contributing sale count, but never the per-month medians
`analyze_sales_performance` computed. So the single most important quantity for §5 — how far ahead
of the runner-up the winning month actually was — **is not in the detail file and cannot be derived
from it**. §6(a)'s sizing was done by proxy (peak-month sale counts and distinct point counts),
which indicates the effect strongly but does not measure it.

This is an instrumentation gap in something built this session, and it is recorded rather than
quietly patched: closing it means adding two columns and re-running 50 rows at ~350 tokens. Whether
that is worth paying before Phase 2 is an owner decision.

**`Diagnostics/` is gitignored, and the box's protocol forbids committing from it.** The audit's
detail file therefore does not leave the box by the route the script suggests. Any future analysis
of it has to run *on* the box and print its answer, which is what the one-liner above does. Scripts
that write analysis artifacts on the box should assume the file stays there.

**`max_xai_calls_per_day` is read once at worker start** (audit A-31). Editing `settings.json`
without a deploy leaves the old value live in every running worker — which is why today's revert
was a deploy and not an edit.

---

## 9. Files Modified

**PR #352 (merged) — stale pricing is never a Prime Pick:**

| file | change |
| :--- | :--- |
| `keepa_deals/pricing_version.py` | `CURRENT_PRICING_PREDICATE`, derived from the stale predicate |
| `keepa_deals/prime_picks_task.py` | Pass 1 filter; `prune_stale_priced_picks` before Pass 1 |
| `wsgi_handler.py` | the read-time clause in the Agent's Choice branch of `/api/deals` |
| `tests/test_prime_picks_stale_pricing.py` | new — 10 cases, 6 red on the parent commit |
| `AGENTS.md` | §7.10 narrowed; new §7.14 |
| `Documentation/System_Architecture.md` | §3.D, "Stale pricing is never a Prime Pick" |
| `Documentation/Feature_Deals_Dashboard.md`, `Data_Logic.md`, `System_State.md` | the rule and its scope |

**PR #352 follow-up (merged):** `System_State.md` line 77 corrected — `prime_picks` **is** rebuilt on
the Janitor's 4-hourly chain. See §2(b).

**PR #353 (merged) — the audit:**

| file | change |
| :--- | :--- |
| `audit_list_at_sources.py` | new — read-only Phase 1 measurement |
| `tests/test_audit_list_at_sources.py` | new — 76 cases, incl. an end-to-end run with Keepa and the bucket faked |
| `Documentation/System_State.md` | the runbook, beside `repair_pricing.py`'s |
| `Documentation/INFERRED_PRICE_LOGIC.md` | §4.A.1 — the open questions, and that no New-offer comparator in the pricing path is contemporaneous with the peak |

The runbook is deliberately **not** in `INFERRED_PRICE_LOGIC.md`: that file is one of the four
`platform_knowledge.py` injects into every AI prompt, uncapped, and an operator runbook does not
belong in a model's context. Owner decision.

Test suite: 263 → **352 passed, 15 subtests**, green at every step.

**No pricing logic was changed today.** `repair_pricing.py`, `token_manager.py`, ingestion and
`PRICING_LOGIC_VERSION` are all untouched.

---

## 10. Open Items

**Unchanged and carried forward:**

1. **§7.1 — skipped rows sort back to the top of every new run.** The attempted set is per-run. The
   231 rows skipped by the completed sweep will re-pay ~7 Keepa tokens each at the start of the
   version-3 re-sweep. Still an owner decision; it now has a date attached, because §6(e) schedules
   that re-sweep.
2. **Trello #143 — the racy xAI counter.** Three `XaiTokenManager` instances writing one state file.
3. **Trello #144 — the reasonableness check fails open on the ERROR path.** `stable_calculations.py`
   catches `(HTTPStatusError, RequestError, Exception)` and returns `True`, so a transient xAI
   outage passes prices exactly as the daily cap used to. PR #346's headroom guard does not cover it.
4. **Trello #145 — Keepa API key rotation** and the audit of other leak paths. PR #347 stopped it
   going forward but cannot unpublish what is already written.
5. **Trello #146 — `backup_db.sh` is a plain `cp` of a WAL database** and can be silently short.

**New:**

6. **The audit's monthly-median gap.** §8. Two columns and a ~350-token re-run would close it.
7. **Phase 2 itself.** §6(a)–(e), decided and unbuilt. A fresh session.
