# Dev Log Entry: Fix Sort Arrows Ignored in the Prime Picks Filtered View

**Date:** September 8, 2026 (second session)
**Files:** `wsgi_handler.py`, `templates/dashboard.html`, `Documentation/Feature_Deals_Dashboard.md`
**Status:** SUCCESS — MERGED TO MAIN (PR #327, `32cd7a1` → `553add4`), DEPLOYED 2026-09-08 21:54 UTC
**Verified live by Tim:** Agent's Choice opens in AI rank order; sort arrows reorder the rows;
reloading with the box ticked preserves the ranking (the `sort=id` fallback works).
**Open:** pre-existing `test_smart_ingestor_batching` failure, unrelated and unchanged.
**Tooling note:** Claude Code (web) against the GitHub sandbox — no `.env`, no `deals.db`, no live
site, so the bug could not be reproduced here. All live evidence supplied by Tim.

---

## 1. Root Cause

The Agent's Choice branch of `/api/deals` built its own SQL string with a hardcoded
`ORDER BY pp.rank ASC` (`wsgi_handler.py:2345`, pre-fix), never referencing the `sort_clause` and
`order` computed above at `:2312-2326`. Those go into `data_query`, executed **only** in the `else`
branch (`:2367`) — the unfiltered path. The chevron still highlighted because the highlight reads
the frontend's `currentSort` (`dashboard.html:721-722`), not row order, and listeners are
re-attached on every render (`:940`): click, fetch and re-render all completed; only the SQL ignored
them.

## 2. The Fix

Option B of two presented: preserve the AI ranking as the default rather than let the user's sort
destroy it. `prime_picks.rank` is exposed as the pseudo-column `Agent_Rank`. The gate is a sibling
boolean *above* the `sort_clause` chain, never inside it, so `sort_clause` cannot hold `pp.rank`
and the alias cannot leak into `data_query`. It also covers `sort=id`, because `fetchDeals()`
(`dashboard.html:1415`) is called with no args on initial load — without that, a reload with the
toggle on would have lost the ranking. Both halves are required: the frontend assignment produces
the behaviour, since a sort param is sent on every request; the backend alone was silently Option A.

## 3. Verification

Verified in the sandbox against the real endpoint on a 4-row scratch DB whose `pp.rank` order
differs from every column order, run on this branch and on a `git worktree` checkout of
`origin/main`: Agent's Choice orderings change; unfiltered orderings and emitted `data_query` SQL
strings are byte-identical to clean HEAD, including the `sort=id` and `sort=Agent_Rank` leak cases.
**A first attempt at that comparison was invalid** — `git stash` found nothing to stash because the
work was already committed, so it compared the branch against itself and reported "identical".
After committing, `stash` is not a clean-HEAD comparison. All three behaviours were then
confirmed on the deployed site by Tim; nothing about this change remains unverified.

## 4. Premise Correction

`Feature_Deals_Dashboard.md` stated Agent's Choice "overrides normal pagination and filtering".
Pagination — correct (`:2361-2363`, single page, no `LIMIT`/`OFFSET`). **Filtering — wrong.** The
branch reuses the same `final_where_clauses` the normal view builds (`:2351`) and *adds* Smart Floor
clauses on top (`:2227-2241`); it bypasses nothing. The doc was also silent on sorting, the one
thing the branch genuinely did override. Both corrected in this PR.

## 5. Hypotheses Discarded

1. **"Sort applied to the full set, filter re-selects after."** No two-step select exists.
2. **"Handler bound to elements the re-render replaces."** Killed by `addEventListeners()` at the
   end of `renderTable` (`:940`), and by the arrow changing state at all.
3. **"`pp.rank` is effectively a Profit sort, so the fix is cosmetic."** Killed by
   `prime_picks_task.py:189` — the score's leading term is `profit² × 100 / cost`, so profit
   dominates, but time decay (half-life 24–168h) and cost move rows independently. Rank encodes
   freshness and capital efficiency a Profit sort drops.

## 6. Files Modified & Left Alone

Backend gate and `ORDER BY` in `wsgi_handler.py`; `syncSortToAgentsChoice()` plus its checkbox and
post-load calls in `templates/dashboard.html`; filtering claim and sort behaviour in
`Documentation/Feature_Deals_Dashboard.md`. Flagged, not touched: `1yr_Avg` and `Percent_Down` are
TEXT (`db_utils.py:245-249`), so sorting them is lexicographic — pre-existing in the unfiltered
view, and Tim's separate card.
