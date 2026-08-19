# Addendum to INFERRED_PRICE_LOGIC.md — `List_at` Seasonal Semantics & the Lightweight Ceiling Clamp

> **How to use this file:** This captures decisions and requirements agreed in the Aug 18 2026 session that are NOT yet implemented. It is the spec for the next round of work on peak-price behaviour. Fold the relevant parts into `INFERRED_PRICE_LOGIC.md` §4 (Price Calculation) once implemented, then archive this addendum. It is living/forward-looking knowledge, deliberately kept out of the dev logs so it is not buried.

## 1. Why this exists

Fixing the lightweight-update key bugs (dev log 2026-08-18b) made the **Amazon ceiling clamp reachable for the first time** — it had been dead code because `list_at_price` always resolved to `0.0`. The clamp is currently gated OFF (`ENABLE_LIGHTWEIGHT_CEILING_CLAMP = False`) because turning it on would silently impose peak-price behaviour that contradicts the intended model below. Do not enable it until this spec is implemented.

## 2. What `List_at` means (owner's model — authoritative)

`List_at` is the **predicted peak-season actual sale price** — the price you expect to *sell your used copy for at its next peak*, derived from true inferred sales (offer-drop + rank-drop), NOT from listing prices.

Key properties it must have:

- **Sticky through the trough.** `List_at` must NOT be dragged down by today's low (off-season) Amazon or market price. A seasonal book selling used at $20 in the trough, that sold at $60 last peak, must keep a `List_at` near $60. Clamping it to ~90% of today's low Amazon price destroys the exact buy-low/sell-high opportunity the tool exists to surface.
- **Predictive, not merely historical.** It is a forecast of the *next* peak, informed by the *history of peaks*. If the most recent peak season came in lower than the prior one, `List_at` should adjust downward as a prediction for the coming season (a book dropping off a syllabus loses value). There is reportedly existing logic using a **~2-year window with a "diminishing returns factor"** to derive this — locate it in the code/docs and reconcile before changing anything.
- **Unprofitable-today is NOT a reason to hide a deal.** For seasonal books, "buy in the trough at a loss-on-paper-today, sell in peak" is the entire strategy. A deal whose `Price_Now` currently exceeds a *correct* seasonal `List_at` may still be a great buy if the peak is meaningfully higher. Filtering purely on today's profit hides the best seasonal buys.

## 3. Two deal archetypes the dashboard must distinguish (and communicate)

1. **Volatile / year-round** — price swings (e.g. ±50%) repeatedly through the year. Strategy: buy low, flip fast at the recurring high. Quick turnover. UI should convey: *"buys low now, fluctuates up to List_at frequently — quick flip."*
2. **Seasonal** — one peak per year. Strategy: buy in trough, **hold 6–8 months**, sell at/just below peak, timed to the season. UI should convey: *"buy now, hold until [peak date]; do not expect to sell at List_at tomorrow."* Must surface the **peak sale DATE**, not just the price, and factor **aged-inventory fees (charges begin after 180 days in Amazon inventory)** into the hold-cost picture.

The system already classifies deals by season vs. "Year-round" and the overlay reportedly shows a peak date — verify both exist and are correct, then make the *strategy implication* explicit in the UI rather than leaving the user to infer it.

## 4. The ceiling clamp — intended behaviour (to replace the gated-off code)

The clamp's original intent (Feb 2026, AGENTS.md §7.8) is sound: a used copy can't realistically be listed above ~90% of Amazon's *new* price. The bug was that the (dead) implementation would have been **destructive** (overwriting stored `List_at`, ratcheting down) and used the **1-year minimum** Amazon price instead of current.

Required semantics when re-enabled:
1. **Non-destructive.** Never overwrite the stored inferred/predicted `List_at`. Any ceiling is applied for *display / recommendation / profit-calc comparison only*, so the true peak survives and is reused when the season returns.
2. **Correct comparator.** Use current Amazon New price per §7.8, not the 1-year minimum (which drags the ceiling down on any past dip).
3. **Floor guard.** Never present or persist a recommendation whose sell price is below the buy price (`Price_Now`). If the ceiling would force sell < buy, drop/hide the recommendation rather than record a guaranteed loss.
4. **Season-aware.** The ceiling comparison must not fire off-season in a way that hides valid seasonal holds (see §2). Reconcile the "seasonal peak can validly be 200–400% above the 3-yr average" allowance — currently the >3x trip-wire divides by *current used* while the allowance is written against the *3-yr average*; align the denominators.

## 5. Open technical items feeding this (from the Aug 18 session)

- Confirm/locate the existing 2-year "diminishing returns" peak logic before touching peak derivation.
- The **3-sales-in-3-months structural trap**: with exactly 3 sane sales across 3 distinct months, "peak-month median" becomes the single highest sale ever (IQR can't trim at n=3). Consider requiring a minimum number of sane sales *in the peak month* before trusting it, or reconciling peak vs. overall median.
- The **`season='-'` bug**: on the sparse+suspicious path, `peak_season_str` stays `'-'` and is sent to the XAI reasonableness check, asking the model to judge seasonality with no season — a mechanism for wrongly rejecting valid seasonal peaks. (Latent; the XAI path showed 0 rejections in the log, but fix when touching this area.)

## 6. Explicitly deferred

Everything in this addendum is a *future* task, to be specified and scheduled deliberately — not bundled with mechanical bug fixes. The clamp stays OFF until §4 is implemented.
