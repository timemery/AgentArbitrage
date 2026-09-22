"""Prime Picks must never present a deal whose pricing was not repaired.

WHY THIS FILE EXISTS
--------------------
Measured on the box, 2026-09-22. The pricing repair sweep (`repair_pricing.py`,
Trello #139) finished its 2026-09-21 run having repaired 3,769 rows, SKIPPED 231
and left 232 stale. Prime Picks then rebuilt at 12:00 UTC with four picks, and
pick #4 - ASIN 1418548839, `List_at` 219.66 - carried `Pricing_Logic_Version`
NULL. The sweep's skip manifest recorded it as "heavy processing returned nothing
(usually: no used offer)", so its `List_at` was still whatever the pre-2026-09-12
pricing logic wrote: the exact number the sweep exists to replace.

That is not a one-off. A skipped row keeps its old prices indefinitely
(`Dev_Logs/2026-09-17_Pricing_Repair_Sweep.md` 7.7), so it stays eligible for
selection on every subsequent run, forever.

THE INVARIANT
-------------
No row with stale pricing is ever shown as a Prime Pick, on ANY path:

1.  a normal run,
2.  a run where Pass 1 finds few or zero eligible candidates,
3.  the Pass 2 failure path, which deliberately preserves the previous cache.

Paths 2 and 3 matter because neither writes to `prime_picks` at all. Filtering
Pass 1 alone fixes only path 1 - a pick chosen before the filter existed, or
before a `PRICING_LOGIC_VERSION` bump re-staled the table, survives every run
that takes path 2 or 3.

So the invariant is held in two places, both reading the SAME predicate from
`keepa_deals/pricing_version.py`:

*   `generate_prime_picks` filters Pass 1 (what may ENTER the cache) and evicts
    stale entries before it does anything else (what may STAY in it).
*   the Agent's Choice branch of `/api/deals` filters at read time (what may be
    SHOWN from it), which is what closes the gap between a version bump and the
    next four-hourly run.

These tests FAIL on the parent commit, where none of those three guards exist.
"""

import ast
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.pricing_version import (  # noqa: E402
    CURRENT_PRICING_PREDICATE,
    PRICING_LOGIC_VERSION,
    PRICING_VERSION_COLUMN,
    STALE_PRICING_PREDICATE,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Only the columns Pass 1, the scoring loop and the Agent's Choice read path
# actually touch. The full deals table is 246 columns wide; none of the others
# participate in this invariant.
DEALS_SCHEMA = """
    CREATE TABLE deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ASIN TEXT UNIQUE,
        Title TEXT,
        Profit REAL,
        All_in_Cost REAL,
        List_at REAL,
        "1yr_Avg" TEXT,
        Deal_Trust TEXT,
        Percent_Down TEXT,
        Seller_Quality_Score TEXT,
        Margin REAL,
        Sales_Rank_Current INTEGER,
        Sales_Rank_Drops_last_180_days INTEGER,
        Offers TEXT,
        Used_Offer_Count_Current TEXT,
        Used_Offer_Count_365_days_avg TEXT,
        Detailed_Seasonality TEXT,
        last_seen_utc TEXT,
        Deal_found TEXT,
        AMZ TEXT,
        "Pricing_Logic_Version" INTEGER
    )
"""

PRIME_PICKS_SCHEMA = """
    CREATE TABLE prime_picks (
        asin TEXT PRIMARY KEY,
        rank INTEGER,
        score REAL,
        generated_at TIMESTAMP,
        run_id TEXT
    )
"""

# A row that clears every other Pass 1 threshold, so the only thing any of these
# tests can be measuring is the pricing version.
#   Profit 40 >= 15 | ROI 66.7% in [20, 300] | Deal Trust 80 >= 50
#   List_at 200 in (0, 500] | 1yr_Avg present | rank well under the year-round cap
#   offers falling (5 now vs 8 avg), so the trend modifier is a bonus, not a drop
CANDIDATE = dict(
    Title='A Perfectly Ordinary Book',
    Profit=40.0,
    All_in_Cost=60.0,
    List_at=200.0,
    _1yr_Avg='250.00',
    Deal_Trust='80%',
    Percent_Down='20',
    Seller_Quality_Score='0.9',
    Margin=20.0,
    Sales_Rank_Current=50000,
    Sales_Rank_Drops_last_180_days=12,
    Offers='5',
    Used_Offer_Count_Current='5',
    Used_Offer_Count_365_days_avg='8',
    Detailed_Seasonality='Year-round',
    last_seen_utc='2026-09-22T10:00:00+00:00',
    Deal_found='2026-09-22T10:00:00+00:00',
    AMZ=None,
)


def insert_deal(conn, asin, version):
    """Insert an otherwise-identical candidate carrying `version`."""
    conn.execute(
        """
        INSERT INTO deals (
            ASIN, Title, Profit, All_in_Cost, List_at, "1yr_Avg", Deal_Trust,
            Percent_Down, Seller_Quality_Score, Margin, Sales_Rank_Current,
            Sales_Rank_Drops_last_180_days, Offers, Used_Offer_Count_Current,
            Used_Offer_Count_365_days_avg, Detailed_Seasonality, last_seen_utc,
            Deal_found, AMZ, "Pricing_Logic_Version"
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asin, CANDIDATE['Title'], CANDIDATE['Profit'], CANDIDATE['All_in_Cost'],
            CANDIDATE['List_at'], CANDIDATE['_1yr_Avg'], CANDIDATE['Deal_Trust'],
            CANDIDATE['Percent_Down'], CANDIDATE['Seller_Quality_Score'],
            CANDIDATE['Margin'], CANDIDATE['Sales_Rank_Current'],
            CANDIDATE['Sales_Rank_Drops_last_180_days'], CANDIDATE['Offers'],
            CANDIDATE['Used_Offer_Count_Current'],
            CANDIDATE['Used_Offer_Count_365_days_avg'],
            CANDIDATE['Detailed_Seasonality'], CANDIDATE['last_seen_utc'],
            CANDIDATE['Deal_found'], CANDIDATE['AMZ'], version,
        ),
    )


def cache_pick(conn, asin, rank):
    conn.execute(
        "INSERT INTO prime_picks (asin, rank, score, generated_at, run_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (asin, rank, 1000.0, '2026-09-22T12:00:00+00:00', 'previous-run'))


def xai_selecting(*asins):
    """An xAI response object that selects exactly `asins`."""
    body = {"selected": [{"asin": a, "reason": "ok"} for a in asins],
            "rejected": []}
    return {"choices": [{"message": {"content": json.dumps(body)}}]}


class PrimePicksDbTestCase(unittest.TestCase):
    """A temp DB wired into whichever module under test reads DB_PATH."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(self.db_path)
        conn.execute(DEALS_SCHEMA)
        conn.execute(PRIME_PICKS_SCHEMA)
        conn.commit()
        conn.close()

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            path = self.db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def db(self):
        return sqlite3.connect(self.db_path)

    def cached_asins(self):
        with self.db() as conn:
            return [r[0] for r in conn.execute(
                "SELECT asin FROM prime_picks ORDER BY rank").fetchall()]


class Pass1ExcludesStalePricedRows(PrimePicksDbTestCase):
    """Path 1: a normal run. The stale rows must never reach Pass 2 at all."""

    def run_task(self, xai):
        from keepa_deals import prime_picks_task
        with patch.object(prime_picks_task, 'DB_PATH', self.db_path), \
                patch.object(prime_picks_task, 'get_tiered_strategies',
                             return_value=''), \
                patch.object(prime_picks_task, 'query_xai_api',
                             return_value=xai) as mock_xai:
            prime_picks_task.generate_prime_picks()
        return mock_xai

    def test_a_null_version_row_and_a_lower_version_row_are_both_excluded(self):
        """The two halves of the NULL rule, on one run.

        NULL is ASIN 1418548839's state - the sweep skipped it, so nothing ever
        stamped it. A version BELOW the current one is what every row looks like
        after `PRICING_LOGIC_VERSION` is bumped for the next pricing fix. Both
        mean "priced by logic that is no longer the logic", and the repair sweep
        already treats them identically; so must this.
        """
        with self.db() as conn:
            insert_deal(conn, 'FRESH00001', PRICING_LOGIC_VERSION)
            insert_deal(conn, 'NULLVER001', None)
            insert_deal(conn, 'OLDVER0001', PRICING_LOGIC_VERSION - 1)

        # xAI is told to select all three. If either stale row reaches the cache,
        # it got there through Pass 1, not through the model's judgement.
        mock_xai = self.run_task(
            xai_selecting('FRESH00001', 'NULLVER001', 'OLDVER0001'))

        self.assertEqual(self.cached_asins(), ['FRESH00001'])

        sent = mock_xai.call_args[0][0]['messages'][1]['content']
        self.assertIn('FRESH00001', sent)
        self.assertNotIn('NULLVER001', sent,
                         "a stale row must not even be paid for in Pass 2")
        self.assertNotIn('OLDVER0001', sent)

    def test_a_current_version_row_is_still_selectable(self):
        """The filter must not be a blanket 'reject everything'."""
        with self.db() as conn:
            insert_deal(conn, 'FRESH00001', PRICING_LOGIC_VERSION)
        self.run_task(xai_selecting('FRESH00001'))
        self.assertEqual(self.cached_asins(), ['FRESH00001'])


class TheZeroCandidatePathEvictsStalePicks(PrimePicksDbTestCase):
    """Path 2: Pass 1 finds nothing, so nothing overwrites the cache."""

    def test_a_stale_pick_does_not_survive_a_run_with_no_candidates(self):
        """This is the live failure, one run later.

        With Pass 1 now excluding the stale rows, a table that holds ONLY stale
        rows yields zero candidates - and `generate_prime_picks` returns early
        without touching `prime_picks`. Before the eviction, the previous run's
        stale pick stayed cached and on screen indefinitely, and every
        subsequent run took this same early return.
        """
        with self.db() as conn:
            insert_deal(conn, 'NULLVER001', None)
            cache_pick(conn, 'NULLVER001', 1)

        from keepa_deals import prime_picks_task
        with patch.object(prime_picks_task, 'DB_PATH', self.db_path), \
                patch.object(prime_picks_task, 'get_tiered_strategies',
                             return_value=''), \
                patch.object(prime_picks_task, 'query_xai_api') as mock_xai:
            prime_picks_task.generate_prime_picks()

        self.assertEqual(self.cached_asins(), [])
        mock_xai.assert_not_called()


class ThePass2FailurePathEvictsStalePicks(PrimePicksDbTestCase):
    """Path 3: Pass 2 fails, so the previous cache is preserved on purpose."""

    def test_a_stale_pick_is_evicted_but_a_current_one_is_preserved(self):
        """The graceful fallback keeps its point; it just stops keeping stale rows.

        AGENTS.md 7.10 preserves the last known valid run rather than showing an
        empty list when xAI errors. That stays true - the current-priced pick is
        still there afterwards. What it must no longer preserve is a pick whose
        prices the pipeline has superseded.
        """
        with self.db() as conn:
            insert_deal(conn, 'FRESH00001', PRICING_LOGIC_VERSION)
            insert_deal(conn, 'NULLVER001', None)
            cache_pick(conn, 'FRESH00001', 1)
            cache_pick(conn, 'NULLVER001', 2)

        from keepa_deals import prime_picks_task
        with patch.object(prime_picks_task, 'DB_PATH', self.db_path), \
                patch.object(prime_picks_task, 'get_tiered_strategies',
                             return_value=''), \
                patch.object(prime_picks_task, 'query_xai_api',
                             return_value={'error': 'xAI is down'}):
            prime_picks_task.generate_prime_picks()

        self.assertEqual(self.cached_asins(), ['FRESH00001'])

    def test_an_empty_pass_2_selection_also_evicts(self):
        """The other preserve-the-cache return: Pass 2 succeeds, selects nobody."""
        with self.db() as conn:
            insert_deal(conn, 'FRESH00001', PRICING_LOGIC_VERSION)
            insert_deal(conn, 'NULLVER001', None)
            cache_pick(conn, 'NULLVER001', 1)

        from keepa_deals import prime_picks_task
        with patch.object(prime_picks_task, 'DB_PATH', self.db_path), \
                patch.object(prime_picks_task, 'get_tiered_strategies',
                             return_value=''), \
                patch.object(prime_picks_task, 'query_xai_api',
                             return_value=xai_selecting()):
            prime_picks_task.generate_prime_picks()

        self.assertEqual(self.cached_asins(), [])


class TheReadPathNeverShowsAStalePick(PrimePicksDbTestCase):
    """Whatever is in the cache, Agent's Choice must not render a stale row.

    The eviction above runs only when the task runs - every four hours, chained
    after the Janitor. Bumping `PRICING_LOGIC_VERSION` re-stales the whole table
    the moment it deploys, and that bump is the documented way to schedule the
    next repair sweep (AGENTS.md 7.13), so between the deploy and the next run
    the cache holds picks that are now stale. This clause is what makes the
    invariant true at the moment of display.
    """

    def setUp(self):
        super().setUp()
        import wsgi_handler
        self.wsgi_handler = wsgi_handler
        self._saved_db_path = wsgi_handler.DB_PATH
        wsgi_handler.DB_PATH = self.db_path

    def tearDown(self):
        self.wsgi_handler.DB_PATH = self._saved_db_path
        super().tearDown()

    def agents_choice_asins(self):
        with self.wsgi_handler.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['logged_in'] = True
            response = client.get('/api/deals?agents_choice=true')
            self.assertEqual(response.status_code, 200)
            return [d['ASIN'] for d in json.loads(response.data)['deals']]

    def test_a_cached_stale_pick_is_not_rendered(self):
        with self.db() as conn:
            insert_deal(conn, 'FRESH00001', PRICING_LOGIC_VERSION)
            insert_deal(conn, 'NULLVER001', None)
            insert_deal(conn, 'OLDVER0001', PRICING_LOGIC_VERSION - 1)
            cache_pick(conn, 'FRESH00001', 1)
            cache_pick(conn, 'NULLVER001', 2)
            cache_pick(conn, 'OLDVER0001', 3)

        self.assertEqual(self.agents_choice_asins(), ['FRESH00001'])


class TheRuleIsDefinedOnlyOnce(unittest.TestCase):
    """One definition of "stale", shared, not three spellings of it.

    `repair_pricing.py` decides what to re-fetch and Prime Picks decides what to
    show; if those two ever disagree about what "stale" means, the sweep will be
    repairing one set of rows while the dashboard hides a different one.
    """

    CONSUMERS = ('keepa_deals/prime_picks_task.py', 'wsgi_handler.py',
                 'repair_pricing.py')

    def source(self, relpath):
        with open(os.path.join(REPO_ROOT, relpath), encoding='utf-8') as fh:
            return fh.read()

    @staticmethod
    def docstring_lines(source):
        """Line numbers occupied by module/class/function docstrings.

        Prose is allowed to name the column - `repair_pricing.py`'s own module
        docstring quotes the predicate, and should. Only executable SQL counts as
        a second implementation.
        """
        lines = set()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                continue
            body = getattr(node, 'body', None)
            if not body:
                continue
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                lines.update(range(first.lineno, first.end_lineno + 1))
        return lines

    def test_the_two_predicates_are_exact_negations(self):
        self.assertEqual(CURRENT_PRICING_PREDICATE,
                         'NOT ' + STALE_PRICING_PREDICATE)

    def test_the_predicate_names_the_documented_column(self):
        self.assertIn('"%s"' % PRICING_VERSION_COLUMN, STALE_PRICING_PREDICATE)

    def test_no_consumer_hand_rolls_the_comparison(self):
        """No `"Pricing_Logic_Version" IS NULL OR ... < n` written out in SQL.

        Comments and docstrings may name the column - that is documentation, not
        a second implementation. What must not exist is a second place that
        decides the answer, because a `PRICING_LOGIC_VERSION` bump would then
        move one and not the other.
        """
        hand_rolled = re.compile(
            r'"?%s"?\s*(IS\s+NULL|<)' % PRICING_VERSION_COLUMN, re.IGNORECASE)
        for relpath in self.CONSUMERS:
            source = self.source(relpath)
            prose = self.docstring_lines(source)
            for lineno, line in enumerate(source.splitlines(), 1):
                if line.lstrip().startswith('#') or lineno in prose:
                    continue
                self.assertIsNone(
                    hand_rolled.search(line),
                    "%s:%d hand-rolls the stale-pricing rule; import it from "
                    "keepa_deals.pricing_version instead:\n  %s"
                    % (relpath, lineno, line.strip()))

    def test_prime_picks_reads_the_shared_predicate(self):
        for relpath in ('keepa_deals/prime_picks_task.py', 'wsgi_handler.py'):
            source = self.source(relpath)
            # assertIn's default message would dump the whole file.
            self.assertTrue('pricing_version import' in source,
                            "%s does not import from keepa_deals.pricing_version"
                            % relpath)
            self.assertTrue('CURRENT_PRICING_PREDICATE' in source,
                            "%s does not use CURRENT_PRICING_PREDICATE" % relpath)


if __name__ == '__main__':
    unittest.main()
