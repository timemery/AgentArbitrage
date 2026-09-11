"""Regression test: the stale-rescue and ghost-sweeper cutoffs are format-matched.

Every writer of `last_seen_utc` uses `datetime.now(timezone.utc).isoformat()`, which
puts a 'T' between the date and the time:

    2026-09-08T11:00:00.123456+00:00

Both selection queries used to build their cutoff with SQLite's `datetime('now', ...)`,
which uses a space:

    2026-09-08 11:00:00

SQLite compares those as TEXT. 'T' is 0x54 and ' ' is 0x20, so any row whose UTC DATE
equalled the cutoff's date compared GREATER and never satisfied the '<', no matter what
time of day it carried. A row therefore became eligible not at its intended age but at
the first 00:00 UTC after that -- at age 72h minus its last-seen UTC time of day for the
48-hour rescue, and "not until the next UTC day" for the 1-hour sweeper.

That mattered because `janitor.py` builds its cutoff with `.isoformat()` and so deletes
at 72h to the second. The rescue's intended 24-hour window shrank to between 4 and 24
hours depending on time of day.

FIXTURES ARE DERIVED FROM THE CUTOFF, NOT FROM A FIXED AGE. The first version of this
file seeded rows at `now - 50h` and relied on that landing on the same UTC date as the
`now - 48h` cutoff. That holds for most of the day but is FALSE between 00:00 and
02:00 UTC, when the two straddle midnight, so the tests failed nightly for fixture
reasons rather than for the defect. `_seed_at_start_of_cutoff_day` instead places the
row at 00:00 UTC on the cutoff's own date, which is on that date by construction and
at or before the cutoff instant at every hour of the clock.
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals import smart_ingestor
from keepa_deals.db_utils import get_db_connection


class _FakeTokenManager:
    """Enough of TokenManager for rescue_stale_deals to reach its SELECT."""

    REFILL_RATE_PER_MINUTE = 25

    def request_permission_for_call(self, cost):
        return True

    def update_after_call(self, tokens_left):
        return None


class StaleCutoffFormatTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_deals.db")
        conn = get_db_connection(self.db_path)
        conn.execute(
            "CREATE TABLE deals (id INTEGER PRIMARY KEY, ASIN TEXT, last_seen_utc TIMESTAMP)"
        )
        conn.execute(
            "CREATE TABLE user_restrictions ("
            "  id INTEGER PRIMARY KEY, user_id TEXT, asin TEXT, is_restricted INTEGER)"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _insert(self, asin, seen_dt):
        """Insert one deal, written the way every production writer writes it."""
        conn = get_db_connection(self.db_path)
        conn.execute(
            "INSERT INTO deals (ASIN, last_seen_utc) VALUES (?, ?)",
            (asin, seen_dt.isoformat()),
        )
        conn.commit()
        conn.close()

    def _seed_at_start_of_cutoff_day(self, asin, offset_hours):
        """Seed the one row that separates the two cutoff formats.

        Placed at 00:00 UTC on the cutoff's own date, so it is:
          * on the cutoff's UTC date, which is what makes the 'T' vs ' ' comparison
            decide the outcome; and
          * at or before the cutoff instant, so a correctly formatted cutoff selects it.
        Both hold at every hour of the clock, unlike a fixed age offset.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
        seen = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertLess(seen, cutoff, "fixture premise: row must predate the cutoff")
        self.assertEqual(
            seen.strftime('%Y-%m-%d'), cutoff.strftime('%Y-%m-%d'),
            "fixture premise: row must share the cutoff's UTC date"
        )
        self._insert(asin, seen)

    def _seed_just_inside_window(self, asin, offset_hours):
        """Seed a row one hour NEWER than the cutoff, which must never be selected."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
        self._insert(asin, cutoff + timedelta(hours=1))

    # --- the 48h Stale Rescue ------------------------------------------------

    def test_row_past_48h_on_the_cutoff_date_is_selected(self):
        """The exact row the old cutoff skipped: past 48h, same UTC date as the cutoff."""
        self._seed_at_start_of_cutoff_day('B00STALE48', offset_hours=48)
        self.assertIn(
            'B00STALE48', self._run_rescue_and_capture_selected_asins(),
            "a deal past 48h was not selected for rescue. Its UTC date matches the "
            "cutoff's, so a space-separated cutoff skips it and it keeps ageing toward "
            "the Janitor's 72h deletion."
        )

    def test_row_inside_the_window_is_still_not_selected(self):
        """The fix must not widen the window: an hour short of 48h is not yet stale."""
        self._seed_just_inside_window('B00FRESH47', offset_hours=48)
        self.assertNotIn('B00FRESH47', self._run_rescue_and_capture_selected_asins())

    def _run_rescue_and_capture_selected_asins(self):
        """Run the real rescue, stopping at the Keepa call, and report what it picked.

        `fetch_current_stats_batch` is patched to return nothing, so the function exits
        right after its SELECT. That keeps this test on the query under test and off the
        processing and upsert paths, which `test_lightweight_upsert_preservation.py`
        already covers.
        """
        captured = []

        def _fake_fetch(api_key, asins_list, days=180, offers=20):
            captured.extend(asins_list)
            return None, None, None, None

        with patch.object(smart_ingestor, 'DB_PATH', self.db_path), \
                patch.object(smart_ingestor, 'fetch_current_stats_batch', _fake_fetch):
            smart_ingestor.rescue_stale_deals(_FakeTokenManager(), limit=20)
        return captured

    # --- the 1h Ghost Restriction Sweeper ------------------------------------

    def test_pending_restriction_past_1h_on_the_cutoff_date_is_requeued(self):
        """Same defect at the sweeper, where it cost up to a full extra UTC day."""
        self._seed_at_start_of_cutoff_day('B00STUCK01', offset_hours=1)
        conn = get_db_connection(self.db_path)
        conn.execute(
            "INSERT INTO user_restrictions (user_id, asin, is_restricted) "
            "VALUES ('u1', 'B00STUCK01', NULL)"
        )
        conn.commit()
        conn.close()

        sent = []
        with patch.object(smart_ingestor, 'DB_PATH', self.db_path), \
                patch.object(smart_ingestor.celery, 'send_task',
                             lambda name, args=None, **kw: sent.append(args[0])):
            smart_ingestor.requeue_stuck_restrictions()

        self.assertEqual(
            [['B00STUCK01']], sent,
            "a restriction check pending past 1h was not re-queued. Its UTC date matches "
            "the cutoff's, so a space-separated cutoff holds it until the next UTC day "
            "and the dashboard keeps showing a spinner."
        )


if __name__ == '__main__':
    unittest.main()
