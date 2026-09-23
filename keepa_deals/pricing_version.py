"""The version stamp that says which pricing logic wrote a row's prices.

WHY THIS EXISTS
---------------
On 2026-09-16, answering "which rows still carry pre-fix prices?", every
timestamp and marker column in the deals table was checked and **not one of them
dates a row's pricing**:

* `last_seen_utc` and `source` are rewritten by ALL THREE paths - heavy
  (`smart_ingestor.py:580-581`), light (`:574-575`) and Stale Rescue
  (`:274-275`). `source` records who touched a row LAST, not who priced it, so a
  row priced by the heavy path on 09-10 reads `stale_rescue` today.
* `Deal_found` is Keepa's `creationDate` (`stable_deals.py:83`), not a write time.
* `last_update` is deliberately never populated (AGENTS.md 7.3).
* `Inferred_Sale_Count` looks like it should work and does not. ASIN 0415009804
  carries a count AND a pre-fix price: rows priced between 2026-09-11, when that
  column shipped, and 2026-09-12 16:50 UTC, when the price-association fix went
  live, have both. Confirmed against production.

So the version stamp is the only way to tell a current price from a stale one.

THE NULL RULE, AND WHY IT IS THE OPPOSITE OF THE Inferred_Sale_Count RULE
------------------------------------------------------------------------
**A row whose `Pricing_Logic_Version` is NULL, or lower than
`PRICING_LOGIC_VERSION`, carries STALE PRICING and is due a heavy re-fetch.**
NULL means "priced by unknown logic", which for scheduling purposes is the same
answer as "priced by old logic".

That is deliberately the reverse of the `Inferred_Sale_Count` rule in
`Documentation/INFERRED_PRICE_LOGIC.md` 4.C, which states that a NULL count means
"never computed" and **must never be read as zero and must never be used to hide a
deal**. The two rules do not conflict, because they answer different questions:

    Inferred_Sale_Count  ->  may this deal be SHOWN to a subscriber?
    Pricing_Logic_Version ->  does this row need WORK scheduled against it?

Being unsure about the first must never hide a deal, because hiding a deal on a
guess costs the subscriber a real opportunity. Being unsure about the second
costs about 7 Keepa tokens and re-prices a row that may not have needed it. The
asymmetry in the cost of being wrong is the whole reason the rules differ.

Do not "harmonise" them.

NO BACKFILL
-----------
Every row that exists today lacks this column, and none of them may be given a
value except by actually recomputing their prices. A backfill would have to guess
which logic wrote a row, and guessing is precisely what this column exists to
stop.

BUMPING IT
----------
Raise `PRICING_LOGIC_VERSION` by one whenever a change alters the prices the
pricing pipeline produces - `infer_sale_events`, `analyze_sales_performance`,
`get_1yr_avg_sale_price` or anything they call. `repair_pricing.py` selects on
`version IS NULL OR version < PRICING_LOGIC_VERSION`, so a bump is the entire
mechanism for scheduling the next repair sweep: no new script, no new predicate.

Do NOT bump it for a change that leaves prices identical (a refactor, a log line,
a docs edit). A spurious bump schedules a full re-fetch of every row in the
database.

A bump also has an IMMEDIATE, VISIBLE effect as of September 2026: Prime Picks
reads `CURRENT_PRICING_PREDICATE` below, so the moment a bump deploys, every row
in the table is stale and Agent's Choice empties out - on the next run, and for
read-time display straight away. It refills as the sweep repairs rows. That is
the intended behaviour (an empty Agent's Choice is better than a recommended
price the system knows is superseded), but it is not a subtle change, so expect
it rather than diagnosing it. The main dashboard grid is NOT affected.
"""

# 1 = everything before 2026-09-12 16:50 UTC. Never written by any code; it is
#     the value NULL stands for, recorded here so the NULL rule has a referent.
# 2 = price association takes the last point strictly before the offer drop
#     (PR #340, live 2026-09-12 16:50 UTC), and the xAI sales rescue is gone
#     (PR #342, live 2026-09-16 20:53 UTC).
# 3 = Phase 2 of the 2026-09-22 List at audit, all under one bump so the
#     re-sweep is paid once (AGENTS.md 7.15): the peak-season mode/median scores
#     DISTINCT price points over the peak SEASON (peak month +/-1, pooled
#     across years), and a season with < 2 distinct points is not priced; the
#     peak-window New cap; the Amazon ceiling reads today's price only in the
#     peak month; the AI check fails closed.
# 4 = the peak season chosen by pooled support (best-median eligible +/-1
#     window, not the highest single month); List at capped at 2x the 1yr
#     median of inferred sales; AI check skipped at <= 1.25x that median;
#     thin rows written NULL so the sweep re-evaluates them (AGENTS.md 7.16).
PRICING_LOGIC_VERSION = 4

# The headers.json display name, and the sanitized DB column it becomes. Named
# here so callers and tests cannot drift onto a different spelling.
PRICING_VERSION_HEADER = 'Pricing Logic Version'
PRICING_VERSION_COLUMN = 'Pricing_Logic_Version'

# The selector for "this row's prices are not current". Used by
# repair_pricing.py and pinned by tests/test_pricing_logic_version.py.
STALE_PRICING_PREDICATE = (
    '("{col}" IS NULL OR "{col}" < {version})'.format(
        col=PRICING_VERSION_COLUMN, version=PRICING_LOGIC_VERSION)
)

# The selector for "this row's prices ARE current", derived from the rule above
# rather than restated, so the two can never drift apart.
#
# The scheduling rule and the display rule are the same rule read in opposite
# directions: a row the repair sweep still owes work to is a row whose prices
# nothing has recomputed under the current logic, so it must not be presented as
# a recommendation. Used by Prime Picks - by `generate_prime_picks` Pass 1, which
# decides what may ENTER the cache, and by the Agent's Choice branch of
# `/api/deals`, which decides what may be SHOWN from it.
#
# NOTE this is a display rule for PRIME PICKS ONLY, not for the dashboard at
# large. The main grid still shows stale-priced rows; suppressing them there
# would empty it while a sweep is in flight, and is an owner decision, not this
# predicate's business.
CURRENT_PRICING_PREDICATE = 'NOT {}'.format(STALE_PRICING_PREDICATE)
