"""Regression test for the light-update upsert that nulled 215 columns (A-7).

The bug: `_process_lightweight_update` builds its row from `dict(sqlite3.Row)` off
`SELECT * FROM deals`, so the row is keyed by SANITIZED DB column names ('List_at').
The main Light Update upsert read values back by headers.json DISPLAY name ('List at'),
which resolved to None for 215 of the 246 columns and bound every one as NULL. The
Stale Rescue upsert had the mirror defect: it read sanitized names, so the handful of
freshly computed values that the light path wrote under display names were discarded
and the old rank / offer counts / all-in cost were written back alongside a Profit and
Margin computed from the NEW cost.

Why this test is shaped the way it is: `tests/test_seller_name_logic.py` encoded the
same wrong key assumption in a hand-written fixture, so it stayed green while
production silently failed every lookup. This test therefore takes BOTH contracts from
production code and never from a literal in the test:

  * the column list comes from headers.json through `sanitize_col_name`, the same
    transform `recreate_deals_table()` uses to CREATE the table;
  * the SQL comes from `keepa_deals.db_utils.build_deals_upsert`, the one builder both
    upsert sites in smart_ingestor.py call.

A wrong key convention on either side cannot satisfy it.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import (
    build_deals_upsert,
    sanitize_col_name,
    to_db_keys,
    upsert_deal_rows,
)
from keepa_deals.processing import _process_lightweight_update, clean_numeric_values

HEADERS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'keepa_deals', 'headers.json'
)

TEST_ASIN = 'B00TESTA71'

# Values the mocked Keepa payload should produce, per column. Each differs from the
# seeded value so "fresh value landed" is distinguishable from "old value preserved".
FRESH_RANK = 4321
FRESH_OFFERS = '7'
FRESH_OFFERS_180 = '11'
FRESH_OFFERS_365 = '13'
FRESH_LPC = '2026-09-09 12:00:00'
FRESH_PRICE_NOW_CENTS = 1000  # -> 10.00
FRESH_SELLER_ID = 'A_FRESH_SELLER'


def _load_headers():
    with open(HEADERS_PATH) as f:
        return json.load(f)


def _create_deals_table(conn, headers):
    """Mirror of recreate_deals_table()'s column derivation, minus the file I/O.

    headers.json already carries last_seen_utc and source, so the schema is exactly
    the sanitized header list with nothing appended - which is what makes
    test_upsert_column_list_matches_the_deals_table a real cross-check between the
    schema path and the upsert path rather than a tautology.

    Types are deliberately left permissive (TEXT) because this test asserts on the
    NULL/not-NULL contract and on which value landed, not on SQLite affinity.
    """
    sanitized = [sanitize_col_name(h) for h in headers]
    cols_sql = []
    for col in sanitized:
        if col == 'ASIN':
            cols_sql.append(f'"{col}" TEXT NOT NULL UNIQUE')
        else:
            cols_sql.append(f'"{col}" TEXT')
    conn.execute(
        f"CREATE TABLE deals (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(cols_sql)})"
    )
    return sanitized


def _seed_row(conn, sanitized_columns):
    """Insert one row with a distinct non-NULL sentinel in every single column."""
    # '1' is used as the universal sentinel rather than a descriptive string because
    # clean_numeric_values() coerces any column whose name contains Rank / Count /
    # Price / Cost / Fee / Avg / List and NULLs whatever it cannot parse. A word-shaped
    # sentinel would therefore be nulled by that coercion, not by the upsert, and would
    # make this test fail for a reason unrelated to A-7.
    values = {}
    for col in sanitized_columns:
        values[col] = TEST_ASIN if col == 'ASIN' else '1'
    # A few columns must hold parseable values for the light path's own reads.
    values.update({
        'List_at': '25.00',
        '1yr_Avg': '30.00',
        'Price_Now': '20.00',
        'Seller': 'Old Seller Name',
        'Seller_ID': 'AN_OLD_SELLER',
        'Sales_Rank_Current': '999999',
        'Offers': '1',
        'Offers_180': '2',
        'Offers_365': '3',
        'last_price_change': '2000-01-01 00:00:00',
        'All_in_Cost': '99.99',
        'Min_Listing_Price': '88.88',
    })
    cols = ', '.join(f'"{c}"' for c in sanitized_columns)
    marks = ', '.join('?' * len(sanitized_columns))
    conn.execute(
        f"INSERT INTO deals ({cols}) VALUES ({marks})",
        tuple(values[c] for c in sanitized_columns),
    )
    conn.commit()
    return values


class LightweightUpsertPreservationTest(unittest.TestCase):
    def setUp(self):
        self.headers = _load_headers()
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.conn = sqlite3.connect(self.db_path)
        self.columns = _create_deals_table(self.conn, self.headers)
        self.seeded = _seed_row(self.conn, self.columns)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def _existing_row_as_production_reads_it(self):
        """dict(sqlite3.Row) off SELECT * - exactly how smart_ingestor builds its map."""
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM deals WHERE ASIN = ?", (TEST_ASIN,))
        row = dict(cur.fetchone())
        self.conn.row_factory = None
        row.pop('id', None)
        return row

    def _run_light_update(self, existing_row):
        """Drive the real _process_lightweight_update with mocked field functions."""
        # Patch targets follow where each name is actually BOUND, not where it is
        # defined. processing.py imports the offer-trend helpers and
        # get_used_product_info at module level, so those must be patched on
        # keepa_deals.processing; sales_rank_current / amazon_current /
        # sales_rank_drops_last_30_days / last_price_change are re-imported inside
        # _process_lightweight_update, so those are patched on their source modules.
        # Business settings deliberately come from the real committed settings.json.
        patches = {
            'keepa_deals.processing.get_used_product_info':
                (FRESH_PRICE_NOW_CENTS, FRESH_SELLER_ID, True, 2),
            'keepa_deals.stable_products.sales_rank_current':
                {'Sales Rank - Current': str(FRESH_RANK)},
            'keepa_deals.stable_products.amazon_current': {},
            'keepa_deals.stable_products.sales_rank_drops_last_30_days':
                {'Sales Rank - Drops last 30 days': '5'},
            'keepa_deals.processing.get_offer_count_trend':
                {'Offers': FRESH_OFFERS},
            'keepa_deals.processing.get_offer_count_trend_180':
                {'Offers 180': FRESH_OFFERS_180},
            'keepa_deals.processing.get_offer_count_trend_365':
                {'Offers 365': FRESH_OFFERS_365},
            'keepa_deals.stable_deals.last_price_change':
                {'last price change': FRESH_LPC},
        }
        started = []
        try:
            for target, value in patches.items():
                p = patch(target, return_value=value)
                p.start()
                started.append(p)
            result = _process_lightweight_update(existing_row, {'asin': TEST_ASIN})
        finally:
            for p in reversed(started):
                p.stop()
        self.assertIsNotNone(result, "_process_lightweight_update returned None")
        return clean_numeric_values(result)

    def _upsert(self, row, source):
        row['last_seen_utc'] = '2026-09-09T00:00:00+00:00'
        row['source'] = source
        cur = self.conn.cursor()
        upsert_deal_rows(cur, [row], self.headers)
        self.conn.commit()
        cur.execute("SELECT * FROM deals WHERE ASIN = ?", (TEST_ASIN,))
        names = [d[0] for d in cur.description]
        return dict(zip(names, cur.fetchone()))

    # --- the contract itself -------------------------------------------------

    def test_light_update_upsert_nulls_no_previously_populated_column(self):
        """A-7: every column non-NULL before the light update is non-NULL after."""
        existing = self._existing_row_as_production_reads_it()
        processed = self._run_light_update(existing)
        stored = self._upsert(processed, 'smart_ingestor_light')

        nulled = sorted(
            col for col in self.columns
            if self.seeded.get(col) is not None and stored.get(col) is None
        )
        self.assertEqual(
            [], nulled,
            f"{len(nulled)} column(s) went from populated to NULL across a light "
            f"update: {nulled}"
        )

    def test_upsert_loses_nothing_the_processing_step_produced(self):
        """The upsert must bind every value the light path computed.

        This is the assertion that isolates A-7 from every other transform: under the
        bug the processed row was fully populated and the upsert bound 215 of its
        columns as NULL purely because it looked them up by the wrong name.
        """
        existing = self._existing_row_as_production_reads_it()
        processed = self._run_light_update(existing)
        stored = self._upsert(dict(processed), 'smart_ingestor_light')

        lost = sorted(
            col for col, value in processed.items()
            if value is not None and col in stored and stored[col] is None
        )
        self.assertEqual(
            [], lost,
            f"the upsert dropped {len(lost)} value(s) the light update computed: {lost}"
        )

    def test_light_update_persists_the_critical_dashboard_columns(self):
        """The three columns /api/deals filters on must survive verbatim."""
        existing = self._existing_row_as_production_reads_it()
        processed = self._run_light_update(existing)
        stored = self._upsert(processed, 'smart_ingestor_light')

        for col in ('List_at', '1yr_Avg', 'Deal_Trust'):
            self.assertIsNotNone(
                stored[col],
                f"{col} was nulled; rows with a NULL {col} drop out of /api/deals"
            )

    def test_fresh_values_land_rather_than_the_stale_ones(self):
        """Mirror-image half of A-7: the Stale Rescue must not write back old values."""
        existing = self._existing_row_as_production_reads_it()
        processed = self._run_light_update(existing)
        stored = self._upsert(processed, 'stale_rescue')

        expected = {
            'Sales_Rank_Current': str(FRESH_RANK),
            'Offers': FRESH_OFFERS,
            'Offers_180': FRESH_OFFERS_180,
            'Offers_365': FRESH_OFFERS_365,
            'last_price_change': FRESH_LPC,
            'Seller_ID': FRESH_SELLER_ID,
        }
        for col, want in expected.items():
            self.assertEqual(
                str(stored[col]), str(want),
                f"{col} kept the stale value {stored[col]!r} instead of {want!r}"
            )

        # All_in_Cost is the one that made rows internally inconsistent: Profit and
        # Margin were computed from the new cost while the old cost was stored.
        self.assertNotEqual(
            str(stored['All_in_Cost']), self.seeded['All_in_Cost'],
            "All_in_Cost was written back stale while Profit/Margin used the new cost"
        )
        self.assertIsNotNone(stored['Min_Listing_Price'])

    def test_heavy_path_row_survives_the_shared_upsert(self):
        """The main upsert is shared by BOTH paths, so display-keyed rows must work.

        `smart_ingestor.run()` appends heavy rows (`_process_single_deal`, keyed by
        headers.json DISPLAY names) and light rows (keyed by sanitized DB column
        names) to the same `rows_to_upsert` list. Switching that upsert to sanitized
        keys without re-keying the heavy row would move the data loss from the light
        path onto the heavy path. `to_db_keys` is what makes the two compatible.
        """
        heavy_row = {header: '1' for header in self.headers}
        heavy_row['ASIN'] = TEST_ASIN
        heavy_row['List at'] = '25.00'
        heavy_row['1yr. Avg.'] = '30.00'
        heavy_row['Sales Rank - Current'] = str(FRESH_RANK)
        # The heavy path mixes a few already-sanitized keys into its display-keyed row.
        heavy_row['Seller_Quality_Score'] = '0.9'
        heavy_row['Total_AMZ_fees'] = '4.00'

        stored = self._upsert(to_db_keys(heavy_row), 'smart_ingestor')

        lost = sorted(
            sanitize_col_name(header) for header in self.headers
            if stored.get(sanitize_col_name(header)) is None
        )
        self.assertEqual(
            [], lost,
            f"the shared upsert dropped {len(lost)} heavy-path value(s): {lost}"
        )
        self.assertEqual(stored['List_at'], '25.00')
        self.assertEqual(stored['1yr_Avg'], '30.00')
        self.assertEqual(str(stored['Sales_Rank_Current']), str(FRESH_RANK))
        self.assertEqual(stored['Seller_Quality_Score'], '0.9')

    def test_to_db_keys_is_idempotent_and_collision_free(self):
        """Re-keying must not merge two distinct columns into one."""
        sanitized = [sanitize_col_name(h) for h in self.headers]
        self.assertEqual(
            len(set(sanitized)), len(sanitized),
            "two headers sanitize to the same column name"
        )
        self.assertEqual(
            sanitized, [sanitize_col_name(c) for c in sanitized],
            "sanitize_col_name is not idempotent; re-keying a sanitized row would corrupt it"
        )

    def test_upsert_column_list_matches_the_deals_table(self):
        """The write contract and the schema contract must not drift apart."""
        sanitized, _sql = build_deals_upsert(self.headers)
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(deals)")
        table_columns = {r[1] for r in cur.fetchall()}
        missing = [c for c in sanitized if c not in table_columns]
        self.assertEqual(
            [], missing,
            f"upsert targets columns absent from the deals table: {missing}"
        )

    def test_processed_row_uses_no_display_name_keys(self):
        """No key the light path emits may be a headers.json display name."""
        existing = self._existing_row_as_production_reads_it()
        processed = self._run_light_update(existing)
        offenders = sorted(k for k in processed if sanitize_col_name(k) != k)
        self.assertEqual(
            [], offenders,
            f"light update emitted display-name keys the upsert cannot read: {offenders}"
        )


if __name__ == '__main__':
    unittest.main()
