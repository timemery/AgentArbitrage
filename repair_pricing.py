#!/usr/bin/env python3
"""repair_pricing.py

Re-price every deals row whose prices were written by superseded pricing logic,
by sending it back through the HEAVY path.

Trello #139. Modelled on `cleanup_low_est_rows.py`, which already solved the
preflight, backup and dry-run mechanics this needs.

WHY THIS EXISTS
---------------
`List_at` and `1yr_Avg` are computed in exactly one place, `_process_single_deal`
(`keepa_deals/processing.py`), and nothing else can rebuild them:

  * the LIGHT path never recomputes them - `_process_lightweight_update`
    (`processing.py:405`) has no `infer_sale_events` call at all;
  * the STALE RESCUE routes to that same light path (`smart_ingestor.py:271`),
    and refreshes `last_seen_utc` every time, so a row it keeps reaching is never
    reaped by the Janitor AND never re-priced;
  * `recalculator.py` is API-free and reads the STORED `List_at` (`:125`).

So a row written before a pricing fix keeps its old prices indefinitely. On
2026-09-16 the top 30 rows over $500 in production were all `stale_rescue` with a
NULL `Inferred_Sale_Count` - pre-fix rows, alive, visible, and unrepairable by any
normal cycle.

The heavy path is also unreachable for them by ordinary means: `smart_ingestor`
routes purely on `asin in existing_asins_set` (`smart_ingestor.py:577`), so an
ASIN already in the table ALWAYS takes the light path. This script is what forces
the heavy path onto an existing row.

WHAT IT SELECTS
---------------
    Pricing_Logic_Version IS NULL OR Pricing_Logic_Version < PRICING_LOGIC_VERSION

NULL means "priced by unknown logic", which for scheduling purposes is the same
answer as "priced by old logic". See `keepa_deals/pricing_version.py` for that
rule in full, and for why it is deliberately the opposite of the
`Inferred_Sale_Count` NULL rule.

**This is the whole re-runnability story.** A future pricing fix does not need a
new script or a new predicate: change the pricing logic, bump
`PRICING_LOGIC_VERSION`, re-run this file unchanged. It never needs to know what
changed.

ORDER OF REPAIR
---------------
  1. VISIBLE rows first - the dashboard predicate from `wsgi_handler.py`. These
     are the ones a subscriber is looking at right now, so a bad price here costs
     the most.
  2. Other PRICED rows, `List_at` DESC. Highest stored price first, because an
     inflated price is the failure mode being repaired.
  3. UNPRICED rows last. Nothing is visibly wrong with them; they are swept for
     completeness and to give every surviving row a real `Inferred_Sale_Count`,
     which is what makes a minimum-sale-count floor enforceable later.

IT RUNS FOR DAYS. RUN IT DETACHED.
----------------------------------
    cd /var/www/agentarbitrage
    sudo -u www-data nohup venv/bin/python repair_pricing.py --apply \\
        > /dev/null 2>&1 &

A dry run REQUIRES --limit and is refused without it: it spends Keepa tokens on
every row it touches and writes nothing, so an unbounded one is pure waste.
`--apply` with no --limit is the intended full sweep and is allowed.

Progress (the script keeps its own log, NOT celery_worker.log):

    tail -f Diagnostics/repair_pricing.log

Stop it cleanly - it finishes the batch in flight, commits it, and exits:

    pkill -f repair_pricing.py

Resume - just run the same command again. Repaired rows carry the current version
and drop out of the predicate by themselves, so nothing is redone.

WHAT IT DOES NOT REPAIR
-----------------------
Two columns come from the /deal feed object, which this script cannot fetch for an
arbitrary ASIN: `Deal_found` and `last_price_change` (the dashboard's "Ago"). Their
STORED values are carried forward rather than blanked - see CARRY_FORWARD_COLUMNS
below for the audit that establishes those are the only two.

A row Keepa does not return, or that heavy processing rejects, is left untouched
and recorded in a SKIPPED manifest beside the repaired one. It is attempted once
per run, not once per batch, so an unrepairable row cannot loop.

SAFETY
------
  * Refuses to run as anyone but www-data.
  * Takes a verified backup through SQLite's own backup API before the first
    write. `backup_db.sh` is deliberately NOT used: it is a plain `cp` of a
    WAL-mode database and can miss whatever is sitting in `deals.db-wal`.
  * DRY RUN BY DEFAULT. `--apply` is required to write anything.
  * Shares the Redis token bucket, so it yields to normal ingestion rather than
    racing it. It does NOT take the `smart_ingestor` lock - holding that for days
    would block every ingestion cycle.
  * Stops if the Keepa refill rate drops below 20/min.
  * Stops while xAI calls remain (--xai-headroom, default 50). Past the daily
    cap the AI Reasonableness Check returns True instead of failing, so an
    unchecked price would be stamped as current and never revisited.
  * WAITS OUT a Keepa token recharge rather than stopping. A
    `TokenRechargeError` is a transient dip in a bucket shared with ingestion,
    not a reason to end a multi-day sweep - see WAITING OUT A RECHARGE below.
    Every OTHER exception still stops the run.

THE xAI CAP, NOT KEEPA TOKENS, IS WHAT MAKES THIS TAKE DAYS
-----------------------------------------------------------
Keepa costs ~7 tokens a row: the whole 4,534-row table is ~42 hours at the live
refill rate. The binding constraint is xAI. The sweep makes ~1.7 reasonableness
calls per row (measured: ~15 calls for 9 rows, 2026-09-17), most of them FORCED by
the 3x-of-current-used rule that fires on exactly the inflated rows being repaired.
Against `max_xai_calls_per_day` (1000, shared with ingestion) that is roughly
500-600 rows a day, so a full sweep is about 8-10 calendar days of one run per day.

The daily count resets on the first call after the LOCAL date changes on the box
(`XaiTokenManager._check_and_reset_daily_count` uses `date.today()`), so re-run
after local midnight.

WAITING OUT A RECHARGE
----------------------
The Keepa bucket is shared with normal ingestion, which refills at 25/min, so a
sweep that reserves 50 tokens a batch WILL periodically find the bucket empty.
`TokenManager` does not sleep through a wait longer than 60s: it raises
`TokenRechargeError` so a Celery task can release its lock and let the worker do
something else (`token_manager.py:299`, `:440`). That is right for a task that
runs every 5 minutes. It is wrong for this script, which has nothing else to do
and no scheduler to bring it back.

On 2026-09-17 the live sweep ended after about an hour on
`Recharge needed: 130s` - a 130-second dip ended a run that had days left. So the
recharge is now WAITED OUT: sleep the seconds the exception asks for plus
RECHARGE_WAIT_MARGIN_SECONDS, then retry THE SAME BATCH.

Three properties of that retry matter:

  * The batch is retried from the target list already in memory. It is NOT
    re-selected, because its ASINs were added to the per-run attempted set before
    the fetch - re-selecting would exclude exactly the rows being retried and the
    batch would silently vanish.
  * Every existing stop condition is re-checked before each retry. The wait
    returns to the top of the batch loop, so the xAI headroom guard, the 20/min
    refill floor and SIGTERM all still apply.
  * Consecutive retries are capped (--max-recharge-retries). Hitting the cap is a
    clean, resumable stop with exit 0, not a failure: repaired rows are durable
    and the same command picks up where it left off. The counter resets on the
    first batch that gets through, so a long sweep that dips once an hour never
    accumulates towards it.

DELIBERATELY NOT REQUIRED: that Celery be stopped. This runs for days alongside
normal ingestion by design. `cleanup_low_est_rows.py` demands a quiet database
because it DELETEs; this one upserts single rows through the same helper the
ingestor uses, against a WAL database with `busy_timeout=5000`.
"""

import argparse
import json
import logging
import math
import os
import pwd
import re
import signal
import sqlite3
import sys
import time
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BACKUP_DIR = os.path.join(REPO_ROOT, 'db_backups')
DEFAULT_LOG_PATH = os.path.join(REPO_ROOT, 'Diagnostics', 'repair_pricing.log')
TABLE_NAME = 'deals'
EXPECTED_USER = 'www-data'
SOURCE_MARKER = 'pricing_repair'

# Batch of 5 mirrors COMMIT_BATCH_SIZE in smart_ingestor.py:42, which exists to
# keep a single reservation inside the burst window.
DEFAULT_BATCH_SIZE = 5

# Tokens reserved per ASIN before the fetch.
#
# The ingestor reserves 20 (`smart_ingestor.py:549`). Real measured cost is ~6 for
# the product call plus 1 for the seller call. The reservation is TRANSIENT: it is
# an `incrbyfloat(TOKENS, -cost)` at `token_manager.py:324`, and the very next
# `update_after_call` overwrites the bucket with Keepa's authoritative `tokensLeft`
# (`token_manager.py:545`, `:560`). So over-reserving does not permanently spend
# tokens - it only depresses the bucket between the reserve and the response, which
# is exactly where Recharge Mode can be tripped.
#
# 10 gives comfortable headroom over the measured 7 while keeping a 5-ASIN batch at
# 50 tokens, i.e. at BURST_THRESHOLD rather than well below it.
DEFAULT_RESERVE_PER_ASIN = 10

MIN_REFILL_RATE = 20.0

# --------------------------------------------------------------------------
# Waiting out a Keepa token recharge
# --------------------------------------------------------------------------
#
# WHY THIS EXISTS - THE STOP OBSERVED ON 2026-09-17. The live sweep ended after
# about an hour with
#
#     ERROR Batch failed (Recharge needed: 130s). Stopping; nothing in this
#     batch was written.
#
# a `TokenRechargeError` out of `token_manager.py`. xAI was nowhere near its cap
# (79 of 5000 calls used), so a 130-second dip in a bucket the sweep SHARES with
# ingestion ended a run with days of work left in it.
#
# `TokenManager` raises rather than sleeping whenever the calculated wait exceeds
# 60s (`token_manager.py:299`, `:440`). That is deliberate and correct for the
# Smart Ingestor: it runs every 5 minutes under a Celery lock, so releasing the
# lock and coming back later frees the worker. This script has no lock to release,
# nothing else to do, and no scheduler to bring it back - for it, the same
# exception is just an early exit.
#
# Keepa refills at 25/min and the sweep reserves 50 tokens a batch, so these dips
# recur EVERY run. Waiting them out is the whole difference between a sweep that
# runs for a day and one that runs for an hour.

# Added to the wait the exception asks for. The wait TokenManager computes is
# exactly enough to reach BURST_THRESHOLD; arriving with nothing to spare invites
# an immediate second recharge, and at 25/min this buys ~6 tokens of slack.
RECHARGE_WAIT_MARGIN_SECONDS = 15

# Used when the exception text carries no parsable figure. Both raise sites
# currently embed one ("Recharge needed: 130s", "Insufficient tokens: wait 130s"),
# but the wording is `token_manager.py`'s to change and this script must not stop
# just because it did.
DEFAULT_RECHARGE_WAIT_SECONDS = 60

# Sanity ceiling on a SINGLE wait. Real waits are bounded by BURST_THRESHOLD (50,
# +5 on the reservation path) over the refill rate, and the sweep already stops
# below 20/min, so the realistic maximum is ~165s. This only guards against a
# nonsense figure in the exception text.
MAX_RECHARGE_WAIT_SECONDS = 1800

# The wait is slept in slices this long so SIGTERM is still noticed promptly.
# `pkill -f repair_pricing.py` is the documented clean stop; a single long sleep
# would make it look hung.
RECHARGE_POLL_SECONDS = 5

# Consecutive recharge retries before the sweep gives up and stops CLEANLY.
#
# The counter resets on the first batch that gets through, so it bounds a stall,
# not a long run: a sweep that dips once an hour never accumulates towards it. At
# ~165s a wait, 10 is roughly half an hour of waiting - past which the bucket is
# not dipping, something systemic is wrong, and idling burns nothing but wall
# clock. Stopping then is exit 0 and resumable, exactly like the xAI headroom stop.
DEFAULT_MAX_RECHARGE_RETRIES = 10

# "Recharge needed: 130s" / "Insufficient tokens: wait 130s".
RECHARGE_WAIT_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?\b')

# Spare xAI calls that must remain before the next batch is allowed to start.
#
# WHY THIS EXISTS - THE BLOCKER FOUND ON 2026-09-17. When the daily cap is hit,
# `_query_xai_for_reasonableness` does not fail and does not skip the row: it
# returns True (`stable_calculations.py:76-78`, "Defaulting to reasonable"). The
# price is then accepted unchecked AND stamped `Pricing_Logic_Version = 2`, so it
# drops out of the predicate and THIS SWEEP NEVER REVISITS IT.
#
# That is the worst possible failure for this script. It would silently launder
# exactly the inflated prices it exists to remove, and leave no trace in the data
# that it had done so.
#
# It is not hypothetical. On the 10-row dry run the sweep made ~15 xAI calls for 9
# rows - about 1.7 per row - and most were FORCED by the 3x-of-current-used rule,
# which fires precisely on the inflated rows this sweep targets. Against
# `max_xai_calls_per_day` (1000, shared with normal ingestion) the cap arrives
# after roughly 500-600 rows.
#
# So the sweep stops itself while the check still works. 50 leaves room for the
# batch in flight (5 rows x ~1.7 = ~9 calls) plus concurrent ingestion.
DEFAULT_XAI_HEADROOM = 50

# Measured on the 2026-09-17 dry run: ~15 calls for 9 rows.
XAI_CALLS_PER_ROW = 1.7

# For the refusal message only. Measured cost is ~6 tokens for the product call
# plus 1 for the seller call; the row count is the 2026-09-16 production sizing.
REAL_TOKENS_PER_ASIN = 7
TYPICAL_ROW_COUNT = 4534

logger = logging.getLogger('repair_pricing')


class RepairAbort(Exception):
    """Something is unsafe. Nothing has been written."""


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

# The dashboard's own data-completeness predicate, copied from wsgi_handler.py's
# /api/deals builder. A row matching this is on screen right now.
VISIBLE_PREDICATE = """
    "List_at" IS NOT NULL AND "List_at" > 0
    AND "1yr_Avg" IS NOT NULL
    AND "1yr_Avg" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00')
    AND "1yr_Avg" != 0
    AND CAST(REPLACE(REPLACE("Profit", '$', ''), ',', '') AS REAL) > 0
"""

PRICED_PREDICATE = '"List_at" IS NOT NULL AND "List_at" > 0'


# --------------------------------------------------------------------------
# Deal-feed carry-forward
# --------------------------------------------------------------------------
#
# THE PROBLEM. The ingestor's heavy path does `product_data.update(deal)`
# (`smart_ingestor.py:573`) before calling `_process_single_deal`, so the merged
# dict carries the /deal feed object's keys alongside the /product response. This
# script only has the /product response - the /deal feed cannot be queried for an
# arbitrary ASIN - so any field function reading a deal-only key gets nothing and
# returns its `-` sentinel, which the full-column upsert then writes over a
# perfectly good stored value.
#
# THE AUDIT. Every one of the 67 non-None FUNCTION_LIST entries was checked, by
# source and then empirically by running the whole list twice against the same
# fixture with and without the deal keys (`creationDate`, `currentSince`,
# `current`, `lastUpdate`, `deltaPercent`). Exactly TWO columns differ:
#
#   Deal_found         `deal_found` (stable_deals.py:88) reads `creationDate`;
#                      absent -> returns '-'.
#   last_price_change  `last_price_change` (stable_deals.py:211) is called as
#                      `func(product_data)` - ONE positional argument - so the
#                      merged dict binds to its `deal_object` parameter and its
#                      own `product_data` parameter stays None. Its csv branch
#                      reads that parameter, so the branch never fires, on the
#                      ingestor too (AGENTS.md 7.3). It therefore always falls
#                      back to `deal_object.get('currentSince')` (:252); absent
#                      -> '-'. That is the dashboard's "Ago" column.
#
# `last update` is not affected: FUNCTION_LIST[10] is None and the column is
# deliberately never populated (AGENTS.md 7.3). Every direct read in
# `_process_single_deal` itself - asin, title, manufacturer, fbaFees,
# referralFeePercentage, offers, categoryTree - is a /product key.
#
# THE RULE. Carry the stored value forward ONLY for these two, ONLY when the
# repair could not compute one. This is an explicit allowlist of NON-PRICING
# columns, not a general preservation pass: `List_at`, `1yr_Avg`, `Deal_Trust`,
# `Inferred_Sale_Count`, `Pricing_Logic_Version` and every pricing-derived column
# (`Profit`, `Margin`, `Percent_Down`, ...) must be overwritten, including to
# NULL. Preserving any of those would make this script an expensive no-op.
#
# This is NOT `_merge_db_keyed`. That helper applies the guard to EVERY value it
# merges, which is right for the light path and exactly wrong here.
CARRY_FORWARD_COLUMNS = ('Deal_found', 'last_price_change')


def build_target_sql(stale_predicate):
    """The ordered target query. Re-run per batch, never snapshotted.

    Re-deriving per batch matters for two independent reasons. The Janitor deletes
    on `last_seen_utc < cutoff` every 4 hours (`janitor.py:25`), so a snapshot
    taken at the start of a multi-day run would send tokens after ASINs that no
    longer exist. And normal ingestion keeps writing, so the visible set moves.
    """
    carried = ''.join('               "{c}" AS stored_{c},\n'.format(c=c)
                      for c in CARRY_FORWARD_COLUMNS)
    return """
        SELECT "ASIN",
               "List_at"              AS old_list_at,
               "1yr_Avg"              AS old_1yr_avg,
               "Inferred_Sale_Count"  AS old_count,
               "Deal_Trust"           AS old_trust,
{carried}               CASE
                   WHEN {visible} THEN 0
                   WHEN {priced}  THEN 1
                   ELSE 2
               END AS tier
        FROM {table}
        WHERE {stale}
          AND "ASIN" NOT IN (SELECT asin FROM attempted_this_run)
        ORDER BY tier ASC,
                 CASE WHEN {priced} THEN "List_at" ELSE 0 END DESC,
                 "ASIN" ASC
        LIMIT ?
    """.format(carried=carried, visible=VISIBLE_PREDICATE.strip(),
               priced=PRICED_PREDICATE, table=TABLE_NAME, stale=stale_predicate)


PROGRESS_SQL = """
SELECT COALESCE(CAST("Pricing_Logic_Version" AS TEXT), 'NULL (stale)') AS version,
       COUNT(*)                                                        AS rows,
       SUM(CASE WHEN "List_at" > 0 THEN 1 ELSE 0 END)                  AS priced,
       ROUND(AVG(CASE WHEN "List_at" > 0 THEN "List_at" END), 2)       AS avg_list_at,
       SUM(CASE WHEN "List_at" >= 1000 THEN 1 ELSE 0 END)              AS four_figure
FROM deals
GROUP BY 1
ORDER BY 1;
"""


# --------------------------------------------------------------------------
# Preflight, backup
# --------------------------------------------------------------------------

def xai_calls_remaining():
    """Spare xAI calls before the daily cap, as conservatively as this can be known.

    Reads the SAME in-process `XaiTokenManager` the reasonableness check uses -
    `keepa_deals.stable_calculations.xai_token_manager`, constructed at module
    import (`stable_calculations.py:23`) - so the number reflects the counter that
    will actually deny the next call.

    TWO CAVEATS, both deliberate and both worth knowing before trusting the number.

    1.  THE IN-PROCESS COUNT UNDER-REPORTS. `XaiTokenManager` reads
        `xai_token_state.json` once, at construction, and thereafter increments its
        own in-memory `calls_today`. Three separate instances exist
        (`stable_calculations.py:23`, `seasonality_classifier.py:14`,
        `xai_sales_inference.py:12`), and normal ingestion is writing the same file
        concurrently. So this process's count sees its own calls plus whatever was
        on disk when it started - never ingestion's since. Under-reporting means
        the guard would fire LATE, which is the dangerous direction, so the on-disk
        value is folded in as a floor. That is strictly safer than the in-process
        count alone and costs one small file read per batch.
        (The underlying raciness is Trello #143 and is NOT fixed here.)

    2.  THE STATE PATH IS RELATIVE. `XaiTokenManager.__init__` defaults to
        `state_path='xai_token_state.json'`, resolved against the PROCESS's working
        directory. Run this script from anywhere but the application root and it
        reads a different file - one that does not exist - and the count starts at
        zero while ingestion's real count keeps climbing. Hence the CWD check in
        `preflight`.
    """
    from keepa_deals.stable_calculations import xai_token_manager as manager

    limit = manager.daily_limit
    in_process = manager.state.get('calls_today', 0)

    on_disk = 0
    try:
        with open(manager.state_path) as fh:
            disk_state = json.load(fh)
        if disk_state.get('last_reset_date') == str(date.today()):
            on_disk = disk_state.get('calls_today', 0)
    except (IOError, OSError, ValueError):
        # No readable state file: the in-process count is all there is. Not fatal -
        # it is the value the manager itself will enforce against.
        pass

    used = max(in_process, on_disk)
    return max(0, limit - used), used, limit


def _estimated_full_sweep_tokens():
    """A rough token figure for the refusal message, from the sizing on record.

    Deliberately a constant rather than a query: the refusal fires BEFORE
    preflight, so the database has not been validated yet and must not be touched.
    An order of magnitude is all this number needs to convey.
    """
    return TYPICAL_ROW_COUNT * REAL_TOKENS_PER_ASIN


def _running_user():
    return pwd.getpwuid(os.geteuid()).pw_name


def preflight(db_path):
    """Aborts unless it is safe to touch deals.db. Nothing here writes anything."""
    logger.info("=" * 70)
    logger.info("PREFLIGHT")
    logger.info("=" * 70)

    user = _running_user()
    if user != EXPECTED_USER:
        raise RepairAbort(
            "This script is running as '{actual}', not '{expected}'.\n"
            "Everything on the box that touches deals.db runs as {expected}, and a "
            "run as another user leaves the database, its -wal and its -shm files "
            "owned by that user, which silently breaks Celery and Apache.\n"
            "Re-run as:  sudo -u {expected} venv/bin/python repair_pricing.py"
            .format(actual=user, expected=EXPECTED_USER)
        )
    logger.info("  Running as: %s - OK", user)

    # Celery is NOT required to be stopped. See the module docstring.
    logger.info("  Celery may keep running; this script shares the token bucket "
                "and does not take the smart_ingestor lock.")

    if not os.path.exists(db_path):
        raise RepairAbort("Database not found at '{}'.".format(db_path))
    logger.info("  Database: %s - OK", db_path)

    # The xAI counter's state path is RELATIVE (`XaiTokenManager.__init__`
    # defaults to 'xai_token_state.json'), so it resolves against this process's
    # working directory. Started from elsewhere, the headroom check reads a file
    # that does not exist, counts zero, and never fires - which is exactly the
    # silent failure it was added to prevent.
    if os.path.realpath(os.getcwd()) != os.path.realpath(REPO_ROOT):
        raise RepairAbort(
            "Working directory is '{cwd}', not the application root '{root}'.\n"
            "The xAI daily-call state file is read by a RELATIVE path, so from "
            "anywhere else the headroom guard silently counts zero calls used "
            "and never stops the sweep.\n"
            "Re-run as:  cd {root} && sudo -u {user} venv/bin/python "
            "repair_pricing.py"
            .format(cwd=os.getcwd(), root=REPO_ROOT, user=EXPECTED_USER))
    logger.info("  Working directory is the application root - OK")

    spare, used, limit = xai_calls_remaining()
    logger.info("  xAI daily calls: %d of %d used, %d spare", used, limit, spare)

    if not os.getenv('KEEPA_API_KEY'):
        raise RepairAbort(
            "KEEPA_API_KEY is not set. Run from the application root so .env is "
            "found, or export it. Nothing has been read or written."
        )
    logger.info("  KEEPA_API_KEY present - OK")


def backup_database(db_path, backup_dir, timestamp):
    """Consistent copy via SQLite's backup API, verified by row count.

    `backup_db.sh` is deliberately not used. It is a plain `cp` of a WAL-mode
    database (`backup_db.sh:8`), so it can produce a silently short backup that
    misses whatever is sitting in deals.db-wal. The backup API reads through the
    WAL and produces a consistent file.
    """
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(
        backup_dir, '{name}.pricing-repair-{ts}.bak'.format(
            name=os.path.basename(db_path), ts=timestamp))
    if os.path.exists(backup_path):
        raise RepairAbort(
            "A backup already exists at '{}'. Refusing to overwrite it."
            .format(backup_path))

    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    except sqlite3.Error as exc:
        raise RepairAbort(
            "The database backup failed ({}). Nothing has been written."
            .format(exc))

    live = _scalar(db_path, 'SELECT COUNT(*) FROM {}'.format(TABLE_NAME))
    kept = _scalar(backup_path, 'SELECT COUNT(*) FROM {}'.format(TABLE_NAME))
    if live != kept:
        raise RepairAbort(
            "Backup verification failed: live has {} rows, backup has {}. "
            "Nothing has been written.".format(live, kept))

    logger.info("  Backup: %s (%d rows, verified)", backup_path, kept)
    return backup_path


def _scalar(db_path, sql):
    con = sqlite3.connect('file:{}?mode=ro'.format(db_path), uri=True)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------

class GracefulStop:
    """Set a flag on SIGTERM/SIGINT; the batch loop checks it between batches.

    Stopping mid-batch would leave Keepa tokens spent on rows that were never
    written. Stopping BETWEEN batches loses nothing: the batch just committed is
    durable, and the predicate excludes it on the next run.
    """

    def __init__(self):
        self.requested = False
        signal.signal(signal.SIGTERM, self._handle)
        signal.signal(signal.SIGINT, self._handle)

    def _handle(self, signum, _frame):
        name = signal.Signals(signum).name
        if self.requested:
            logger.warning("Second %s - exiting immediately.", name)
            sys.exit(130)
        self.requested = True
        logger.warning(
            "%s received. Finishing the batch in flight, committing it, then "
            "exiting. Send it again to exit at once (loses the batch's tokens).",
            name)


def recharge_wait_seconds(exc, margin=RECHARGE_WAIT_MARGIN_SECONDS):
    """How long to sleep for a `TokenRechargeError`, from the exception text.

    `TokenManager` embeds the figure it calculated in the message rather than on
    the exception - "Recharge needed: 130s" (`token_manager.py:299`) and
    "Insufficient tokens: wait 130s" (`:440`). Parsing text is not lovely, but the
    alternative is changing `token_manager.py`, which is out of scope and shared
    with ingestion.

    An unparsable message is NOT a reason to stop: it falls back to
    DEFAULT_RECHARGE_WAIT_SECONDS, waits, and retries like any other recharge.
    """
    match = RECHARGE_WAIT_PATTERN.search(str(exc))
    requested = float(match.group(1)) if match else DEFAULT_RECHARGE_WAIT_SECONDS
    wait = int(math.ceil(max(0.0, requested))) + margin
    return min(wait, MAX_RECHARGE_WAIT_SECONDS)


def sleep_through_recharge(seconds, stop=None, sleep=time.sleep):
    """Sleep in short slices, returning False if a stop was requested part way.

    A single `time.sleep(165)` would ignore SIGTERM for the whole wait, and
    `pkill -f repair_pricing.py` is the documented clean stop. Slicing keeps that
    responsive without threads or signal gymnastics.
    """
    remaining = seconds
    while remaining > 0:
        if stop is not None and stop.requested:
            return False
        slice_seconds = min(RECHARGE_POLL_SECONDS, remaining)
        sleep(slice_seconds)
        remaining -= slice_seconds
    return True


# --------------------------------------------------------------------------
# The repair itself
# --------------------------------------------------------------------------

def fetch_targets(db_path, sql, limit, attempted=()):
    """Next `limit` stale rows, excluding every ASIN already attempted this run.

    WHY THE EXCLUSION EXISTS. A target that Keepa does not return, or whose
    processing raises, or which `_process_single_deal` rejects (no used offer, say)
    is left untouched - so it stays stale and sorts straight back to the TOP of the
    next batch. Without this set an unlimited `--apply` run re-fetches the same
    unrepairable rows forever, burning ~7 tokens each time round, and a dry run with
    `--limit 20` previews the same 5 rows four times.

    The set lives in a TEMP table rather than in bound parameters. Temp tables work
    fine against a read-only main database (they live in a separate temp store), and
    unlike a `NOT IN (?,?,...)` list they have no variable-count ceiling - which
    matters because in the worst case (Keepa unreachable) every row in the table
    ends up in this set.
    """
    con = sqlite3.connect('file:{}?mode=ro'.format(db_path), uri=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute('CREATE TEMP TABLE attempted_this_run (asin TEXT PRIMARY KEY)')
        if attempted:
            con.executemany('INSERT OR IGNORE INTO attempted_this_run VALUES (?)',
                            [(a,) for a in attempted])
        return [dict(r) for r in con.execute(sql, (limit,)).fetchall()]
    finally:
        con.close()


def repair_batch(targets, api_key, xai_api_key, token_manager, reserve_per_asin,
                 apply_changes):
    """Heavy-fetch one batch and return the processed rows.

    This is `smart_ingestor.run()`'s heavy branch, lifted deliberately verbatim so
    the two cannot drift: `_process_single_deal` -> `clean_numeric_values` ->
    `to_db_keys` -> `upsert_deal_rows`.

    `_merge_db_keyed` is NOT used and must never be. That is the LIGHT path's
    preservation helper: it skips a value rather than overwriting a stored one,
    which would protect exactly the stale `List_at` this script exists to replace.
    """
    from keepa_deals.keepa_api import fetch_product_batch
    from keepa_deals.processing import _process_single_deal, clean_numeric_values
    from keepa_deals.db_utils import to_db_keys
    from keepa_deals.seller_info import get_seller_info_for_single_deal
    from keepa_deals.token_manager import TokenRechargeError

    asins = [t['ASIN'] for t in targets]
    token_manager.request_permission_for_call(reserve_per_asin * len(asins))
    resp, _, _, tokens_left = fetch_product_batch(
        api_key, asins, days=365, history=1, offers=20)
    if tokens_left is not None:
        # Reconcile the bucket to Keepa's authoritative figure, replacing the
        # estimate reserved above (token_manager.py:545).
        token_manager.update_after_call(tokens_left)

    if not resp or 'products' not in resp:
        logger.warning("  Fetch returned nothing for %s.", asins)
        return [], [], [(a, 'Keepa returned no products for the batch')
                        for a in asins]

    products = {p['asin']: p for p in resp['products']}
    rows, outcomes, skipped = [], [], []

    for target in targets:
        asin = target['ASIN']
        product = products.get(asin)
        if not product:
            logger.warning("  %s: not returned by Keepa. Left untouched.", asin)
            skipped.append((asin, 'not returned by Keepa'))
            continue
        try:
            seller_cache = get_seller_info_for_single_deal(
                product, api_key, token_manager)
            row = _process_single_deal(product, seller_cache, xai_api_key)
            if not row:
                logger.warning("  %s: heavy processing returned nothing. "
                               "Left untouched.", asin)
                skipped.append((asin, 'heavy processing returned nothing '
                                      '(usually: no used offer)'))
                continue
            row = clean_numeric_values(row)
            row = to_db_keys(row)
            row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
            row['source'] = SOURCE_MARKER
            carry_forward_deal_feed_columns(row, target)
            rows.append(row)
            outcomes.append({
                'ASIN': asin,
                'old_list_at': target['old_list_at'],
                'new_list_at': row.get('List_at'),
                'old_1yr_avg': target['old_1yr_avg'],
                'new_1yr_avg': row.get('1yr_Avg'),
                'old_count': target['old_count'],
                'new_count': row.get('Inferred_Sale_Count'),
                'old_trust': target['old_trust'],
                'new_trust': row.get('Deal_Trust'),
                'tier': target['tier'],
            })
        except TokenRechargeError:
            # NOT this row's fault, and not a reason to record it as unrepairable.
            # `get_seller_info_for_single_deal` reserves tokens of its own
            # (`seller_info.py:45`), so a recharge can surface here as easily as on
            # the batch reservation above. Swallowed into `skipped` it would mark a
            # perfectly repairable row as failed AND keep it out of every later
            # batch this run - and once the caller waits recharges out instead of
            # stopping, that would happen on every dip rather than once.
            #
            # So it goes back to the caller, which sleeps and retries the whole
            # batch. The rows gathered so far are discarded unwritten; that costs
            # their fetch (~7 tokens each, at most a batch's worth) and is the
            # price of not losing them.
            raise
        except Exception as exc:
            logger.error("  %s: heavy processing failed (%s). Left untouched.",
                         asin, exc, exc_info=True)
            skipped.append((asin, 'heavy processing raised: {}'.format(exc)))

    if apply_changes and rows:
        from keepa_deals.db_utils import (get_db_connection, upsert_deal_rows,
                                          DB_PATH, HEADERS_PATH)
        with open(HEADERS_PATH) as fh:
            headers = json.load(fh)
        with get_db_connection(DB_PATH) as con:
            cur = con.cursor()
            upsert_deal_rows(cur, rows, headers)
            con.commit()

    return rows, outcomes, skipped


def carry_forward_deal_feed_columns(row, target):
    """Put back the stored value for the two deal-feed-only columns.

    Only when the repair could not compute one: the heavy path reports "no value"
    in band, under the column's own key, as the string `-`. Writing that through
    the full-column upsert would blank a good stored `Deal_found` or the
    dashboard's "Ago" column on every repaired row.

    Scope is the explicit `CARRY_FORWARD_COLUMNS` allowlist and nothing else. It
    reuses `_is_no_data` from `processing.py` for the sentinel test - that is the
    shared definition of "the field function had nothing", NOT `_merge_db_keyed`,
    which applies the same guard to every column and would preserve the stale
    prices this script exists to replace.
    """
    from keepa_deals.processing import _is_no_data

    for column in CARRY_FORWARD_COLUMNS:
        computed = row.get(column)
        if not _is_no_data(computed):
            continue                      # the repair worked; keep what it found
        stored = target.get('stored_{}'.format(column))
        if _is_no_data(stored):
            continue                      # nothing better to fall back to
        row[column] = stored
    return row


def _fmt(value):
    if value is None:
        return 'NULL'
    return str(value)


def print_outcomes(outcomes, apply_changes):
    verb = 'WROTE' if apply_changes else 'WOULD WRITE'
    for o in outcomes:
        logger.info(
            "  %s [tier %d] %s  List_at %s -> %s | 1yr_Avg %s -> %s | "
            "count %s -> %s | trust %s -> %s",
            verb, o['tier'], o['ASIN'],
            _fmt(o['old_list_at']), _fmt(o['new_list_at']),
            _fmt(o['old_1yr_avg']), _fmt(o['new_1yr_avg']),
            _fmt(o['old_count']), _fmt(o['new_count']),
            _fmt(o['old_trust']), _fmt(o['new_trust']))


def write_manifest(backup_dir, timestamp, mode, asins):
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(
        backup_dir, 'pricing_repair_asins_{}_{}.txt'.format(mode, timestamp))
    with open(path, 'w') as fh:
        fh.write('\n'.join(asins) + ('\n' if asins else ''))
    logger.info("  ASIN manifest: %s (%d)", path, len(asins))
    return path


def write_skip_manifest(backup_dir, timestamp, mode, skipped):
    """Skipped and failed ASINs, with the reason, in their own file.

    Kept separate from the repaired manifest because these rows are still stale
    after the run: they are the follow-up list, not the record of work done.
    """
    if not skipped:
        return None
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(
        backup_dir, 'pricing_repair_skipped_{}_{}.txt'.format(mode, timestamp))
    with open(path, 'w') as fh:
        for asin, reason in skipped:
            fh.write('{}\t{}\n'.format(asin, reason))
    logger.info("  SKIPPED manifest: %s (%d)", path, len(skipped))
    return path


def setup_logging(log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    fmt = logging.Formatter('%(asctime)sZ %(levelname)s %(message)s')
    fmt.converter = time.gmtime
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    # Keep the pipeline's own chatter out of this log; it is extremely verbose and
    # this file has to stay readable across a multi-day run.
    logging.getLogger('keepa_deals').setLevel(logging.WARNING)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Re-price rows whose prices came from superseded pricing "
                    "logic, by forcing them through the heavy path. "
                    "DRY RUN unless --apply is given.")
    parser.add_argument('--apply', action='store_true',
                        help='Actually write. Without this, nothing is written.')
    parser.add_argument('--limit', type=int, default=None,
                        help='Stop after this many rows. REQUIRED for a dry run, '
                             'which is refused without it: every row costs Keepa '
                             'tokens even though nothing is written. Optional '
                             'with --apply, where omitting it means the full '
                             'sweep.')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument('--reserve-per-asin', type=int,
                        default=DEFAULT_RESERVE_PER_ASIN)
    parser.add_argument('--xai-headroom', type=int, default=DEFAULT_XAI_HEADROOM,
                        help='Stop before a batch when fewer than this many xAI '
                             'calls remain against the daily cap. Past the cap '
                             'the AI Reasonableness Check silently returns True, '
                             'so continuing would stamp unchecked prices as '
                             'current. Default %d.' % DEFAULT_XAI_HEADROOM)
    parser.add_argument('--max-recharge-retries', type=int,
                        default=DEFAULT_MAX_RECHARGE_RETRIES,
                        help='Consecutive Keepa recharge waits before the sweep '
                             'stops cleanly (exit 0, resumable). The counter '
                             'resets on the first batch that gets through, so '
                             'this bounds a stall, not a long run. Default %d.'
                             % DEFAULT_MAX_RECHARGE_RETRIES)
    parser.add_argument('--backup-dir', default=DEFAULT_BACKUP_DIR)
    parser.add_argument('--log-file', default=DEFAULT_LOG_PATH)
    args = parser.parse_args(argv)

    setup_logging(args.log_file)
    load_dotenv()

    from keepa_deals.db_utils import DB_PATH
    from keepa_deals.pricing_version import (PRICING_LOGIC_VERSION,
                                             STALE_PRICING_PREDICATE)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    mode = 'apply' if args.apply else 'dryrun'

    logger.info("=" * 70)
    logger.info("repair_pricing.py  mode=%s  target version=%d",
                mode.upper(), PRICING_LOGIC_VERSION)
    logger.info("=" * 70)

    # A dry run with no --limit is refused outright, BEFORE preflight and before
    # anything is read. It would heavy-fetch every stale row - roughly 32,000 Keepa
    # tokens at the 2026-09-16 sizing - and write nothing at all, which is the
    # worst possible combination: maximum spend for zero effect.
    #
    # This used to be survivable by accident, because the dry run stopped after one
    # batch. That workaround only existed to paper over the stuck-row loop; once
    # the attempted set fixed that properly, the dry run began walking the whole
    # table, so the guard has to be explicit.
    #
    # --apply with no --limit is the INTENDED full-sweep invocation and stays
    # allowed: it spends the same tokens but repairs every row it touches.
    if not args.apply and args.limit is None:
        logger.error(
            "REFUSED: a dry run with no --limit would heavy-fetch EVERY stale "
            "row (~%d Keepa tokens at ~7/ASIN) and write nothing.\n"
            "  Preview a sample instead:\n"
            "      repair_pricing.py --limit 10\n"
            "  Or run the real sweep, which writes what it fetches:\n"
            "      repair_pricing.py --apply",
            _estimated_full_sweep_tokens())
        return 1

    if not args.apply:
        logger.info("DRY RUN. Nothing will be written. Keepa tokens ARE spent, "
                    "capped by --limit %d.", args.limit)

    try:
        preflight(DB_PATH)
    except RepairAbort as exc:
        logger.error("ABORTED: %s", exc)
        return 1

    total_stale = _scalar(
        DB_PATH, 'SELECT COUNT(*) FROM {} WHERE {}'.format(
            TABLE_NAME, STALE_PRICING_PREDICATE))
    logger.info("  Stale-pricing rows: %d", total_stale)
    budget = args.limit if args.limit is not None else total_stale
    logger.info("  This run will attempt: %d", min(budget, total_stale))
    logger.info("  Estimated real Keepa cost: ~%d tokens (~7/ASIN)",
                min(budget, total_stale) * 7)

    if args.apply:
        try:
            backup_database(DB_PATH, args.backup_dir, timestamp)
        except RepairAbort as exc:
            logger.error("ABORTED: %s", exc)
            return 1

    api_key = os.getenv('KEEPA_API_KEY')
    xai_api_key = os.getenv('XAI_TOKEN')

    from keepa_deals.token_manager import TokenManager, TokenRechargeError
    # Same construction and sync the ingestor uses (smart_ingestor.py:319-325), so
    # this process shares the one Redis bucket rather than keeping its own count.
    token_manager = TokenManager(api_key)
    if token_manager.should_skip_sync():
        logger.info("  Recharge Mode active and tokens low; skipping the initial "
                    "sync, as the ingestor does.")
    else:
        token_manager.sync_tokens()
    logger.info("  Tokens: %.1f, refill %.1f/min",
                token_manager.tokens, token_manager.REFILL_RATE_PER_MINUTE)

    stop = GracefulStop()
    sql = build_target_sql(STALE_PRICING_PREDICATE)
    done, all_asins, all_skipped = 0, [], []
    # Every ASIN this run has spent tokens on, repaired or not. Excluded from the
    # target query so an unrepairable row is fetched ONCE per run instead of
    # sorting back to the top of every batch forever.
    attempted = set()
    # A batch that hit a Keepa recharge and is waiting to be retried. Held in
    # memory deliberately: its ASINs are already in `attempted`, so re-selecting
    # it through `fetch_targets` would exclude the very rows being retried.
    pending_targets = None
    consecutive_recharge_waits = 0

    while True:
        if stop.requested:
            logger.info("Stop requested. Exiting between batches.")
            break
        if args.limit is not None and done >= args.limit:
            logger.info("Reached --limit %d.", args.limit)
            break
        spare, used, limit = xai_calls_remaining()
        if spare < args.xai_headroom:
            logger.warning("=" * 70)
            logger.warning(
                "STOPPING: xAI daily limit nearly reached (%d of %d used, %d "
                "spare, headroom %d).", used, limit, spare, args.xai_headroom)
            logger.warning(
                "Continuing would be WORSE than stopping. Past the cap, the AI "
                "Reasonableness Check does not fail or skip - it returns True "
                "(stable_calculations.py:76), so an inflated price would be")
            logger.warning(
                "accepted unchecked AND stamped Pricing_Logic_Version=%d, which "
                "drops it out of the predicate. This sweep would never revisit "
                "it.", PRICING_LOGIC_VERSION)
            logger.warning(
                "Nothing has been written for this batch. Re-run the same "
                "command after the daily reset (local midnight on the box); "
                "repaired rows are already durable and are not redone.")
            logger.warning("=" * 70)
            break

        if token_manager.REFILL_RATE_PER_MINUTE < MIN_REFILL_RATE:
            logger.warning(
                "Refill rate is %.1f/min, below the %.0f/min floor. Stopping so "
                "normal ingestion is not starved. Re-run later; nothing is lost.",
                token_manager.REFILL_RATE_PER_MINUTE, MIN_REFILL_RATE)
            break

        if pending_targets is not None:
            targets = pending_targets
            logger.info("Retrying the same batch of %d after the recharge wait "
                        "(retry %d of %d).", len(targets),
                        consecutive_recharge_waits, args.max_recharge_retries)
        else:
            remaining = (args.batch_size if args.limit is None
                         else min(args.batch_size, args.limit - done))
            targets = fetch_targets(DB_PATH, sql, remaining, attempted)
            if not targets:
                if all_skipped:
                    logger.info("No stale-pricing rows left that this run has not "
                                "already attempted. %d row(s) could not be "
                                "repaired - see the SKIPPED manifest.",
                                len(all_skipped))
                else:
                    logger.info("No stale-pricing rows left.")
                break

            logger.info("Batch of %d (attempted %d / %d, repaired %d, skipped %d)",
                        len(targets), done, total_stale, len(all_asins),
                        len(all_skipped))
            # Mark BEFORE the fetch: a crash mid-batch must not put these rows back
            # at the top of the next batch within this same run.
            attempted.update(t['ASIN'] for t in targets)

        try:
            _, outcomes, skipped = repair_batch(
                targets, api_key, xai_api_key, token_manager,
                args.reserve_per_asin, args.apply)
        except TokenRechargeError as exc:
            # A transient dip in the bucket this sweep shares with ingestion - not
            # a failure, and not a reason to end a multi-day run. Nothing in this
            # batch was written, so the same targets can simply be tried again.
            consecutive_recharge_waits += 1
            if consecutive_recharge_waits > args.max_recharge_retries:
                logger.warning("=" * 70)
                logger.warning(
                    "STOPPING: %d consecutive Keepa recharge waits (%s). The "
                    "bucket is not recovering, so this is a stall rather than a "
                    "dip.", consecutive_recharge_waits - 1, exc)
                logger.warning(
                    "Nothing has been written for this batch. Repaired rows are "
                    "already durable; re-run the same command once tokens are "
                    "back and it picks up where it left off.")
                logger.warning("=" * 70)
                break
            wait = recharge_wait_seconds(exc)
            logger.warning(
                "Keepa recharge needed (%s). Waiting %ds (+%ds margin), then "
                "retrying the same batch of %d. Recharge wait %d of %d.",
                exc, wait, RECHARGE_WAIT_MARGIN_SECONDS, len(targets),
                consecutive_recharge_waits, args.max_recharge_retries)
            pending_targets = targets
            if not sleep_through_recharge(wait, stop):
                logger.info("Stop requested during the recharge wait.")
            continue
        except Exception as exc:
            logger.error("Batch failed (%s). Stopping; nothing in this batch was "
                         "written.", exc, exc_info=True)
            break

        pending_targets = None
        consecutive_recharge_waits = 0

        print_outcomes(outcomes, args.apply)
        all_asins.extend(o['ASIN'] for o in outcomes)
        all_skipped.extend(skipped)
        for asin, reason in skipped:
            logger.warning("  SKIPPED %s: %s", asin, reason)
        done += len(targets)

    write_manifest(args.backup_dir, timestamp, mode, all_asins)
    write_skip_manifest(args.backup_dir, timestamp, mode, all_skipped)

    logger.info("=" * 70)
    logger.info("%s: %d row(s) %s, %d skipped, %d attempted.",
                mode.upper(), len(all_asins),
                'repaired' if args.apply else 'previewed',
                len(all_skipped), len(attempted))
    remaining_stale = _scalar(
        DB_PATH, 'SELECT COUNT(*) FROM {} WHERE {}'.format(
            TABLE_NAME, STALE_PRICING_PREDICATE))
    logger.info("Stale-pricing rows remaining: %d", remaining_stale)
    if args.apply and remaining_stale == 0:
        logger.info("")
        logger.info("*** REFRESH PRIME PICKS NOW. ***")
        logger.info("The prime_picks table stores a SELECTION made against the "
                    "old prices. It is not beat-scheduled, so it will not")
        logger.info("self-heal. POST to /api/prime_picks/refresh, or use the "
                    "button on the dashboard.")
    elif args.apply:
        logger.info("Re-run the same command to continue. Repaired rows drop out "
                    "of the predicate by themselves.")
    logger.info("=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
