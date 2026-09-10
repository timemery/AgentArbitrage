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

These tests drive the production functions with a patched DB_PATH, and pin the ONE case
that separates the two formats: a row old enough to qualify whose UTC date is the same
as the cutoff's. Against the pre-fix code both fail.
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

    def _seed_deal(self, asin, age_hours):
        """Insert one deal last seen `age_hours` ago, written the way production writes."""
        seen = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
        conn = get_db_connection(self.db_path)
        conn.execute(
            "INSERT INTO deals (ASIN, last_seen_utc) VALUES (?, ?)", (asin, seen)
        )
        conn.commit()
        conn.close()
        return seen

    @staticmethod
    def _same_utc_date_as_cutoff(seen_iso, offset_hours):
        """True when this row is the case that separates the two cutoff formats."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
        return seen_iso[:10] == cutoff.strftime('%Y-%m-%d')

    # --- the 48h Stale Rescue ------------------------------------------------

    def test_row_50h_old_on_the_cutoff_date_is_selected(self):
        """The exact row the old cutoff skipped: past 48h, same UTC date as the cutoff.

        A 50-hour-old row is always 2 hours after the 48-hour cutoff instant, so it
        always shares the cutoff's UTC date. Under the space-separated cutoff its 'T'
        sorted after the cutoff's space and it was never selected.
        """
        seen = self._seed_deal('B00STALE50', age_hours=50)
        self.assertTrue(
            self._same_utc_date_as_cutoff(seen, 48),
            "fixture is not exercising the bug: row date differs from the cutoff date"
        )

        selected = self._run_rescue_and_capture_selected_asins()
        self.assertIn(
            'B00STALE50', selected,
            "a 50h-old deal was not selected for rescue. Its UTC date matches the "
            "cutoff's, so a space-separated cutoff skips it and it keeps ageing "
            "toward the Janitor's 72h deletion."
        )

    def test_row_inside_the_window_is_still_not_selected(self):
        """The fix must not widen the window: 47h is not yet stale."""
        self._seed_deal('B00FRESH47', age_hours=47)
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

    def test_pending_restriction_2h_old_on_the_cutoff_date_is_requeued(self):
        """Same defect at the sweeper, where it cost up to a full extra UTC day."""
        seen = self._seed_deal('B00STUCK02', age_hours=2)
        self.assertTrue(
            self._same_utc_date_as_cutoff(seen, 1),
            "fixture is not exercising the bug: row date differs from the cutoff date"
        )
        conn = get_db_connection(self.db_path)
        conn.execute(
            "INSERT INTO user_restrictions (user_id, asin, is_restricted) "
            "VALUES ('u1', 'B00STUCK02', NULL)"
        )
        conn.commit()
        conn.close()

        sent = []
        with patch.object(smart_ingestor, 'DB_PATH', self.db_path), \
                patch.object(smart_ingestor.celery, 'send_task',
                             lambda name, args=None, **kw: sent.append(args[0])):
            smart_ingestor.requeue_stuck_restrictions()

        self.assertEqual(
            [['B00STUCK02']], sent,
            "a restriction check pending for 2h was not re-queued. Its UTC date matches "
            "the cutoff's, so a space-separated cutoff holds it until the next UTC day "
            "and the dashboard keeps showing a spinner."
        )


if __name__ == '__main__':
    unittest.main()
