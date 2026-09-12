import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals import smart_ingestor
from keepa_deals.token_manager import TokenRechargeError

class TestSmartIngestorBatching(unittest.TestCase):
    """Peek/Commit batch sizing, across every dynamic tier.

    The peek batch size is NOT a constant. `smart_ingestor.run()` scales it down from
    SCAN_BATCH_SIZE by the token refill rate Keepa reports, to keep one peek inside a
    refillable token budget (`smart_ingestor.py`, "Dynamic Batch Sizing"):

        refill rate      peek batch
        < 10/min                  1
        < 20/min                 20
        < 30/min                 15
        >= 30/min                50   (SCAN_BATCH_SIZE)

    The 15-cap for 20-29/min was added deliberately for the live 25/min Keepa plan: a
    50-ASIN peek at days=365, offers=20 costs roughly 386 tokens, far past the burst
    budget, and drives the account into deep deficit.

    This test asserted a flat 50 and so failed from the day that tier was added. It was
    the one permanently-red case in the suite, which is why `run_tests.sh` could not be
    used as a gate. Corrected 2026-09-12 to assert the tiers the code actually has.
    """

    # The live Keepa plan reports 25/min, so this is the tier production runs in.
    LIVE_REFILL_RATE = 25

    def _run_ingestor(self, refill_rate, deal_count=100):
        """Run smart_ingestor.run() against mocked Keepa/DB/Redis at `refill_rate`.

        Returns (peek_calls, started), where `peek_calls` holds the *non-empty*
        fetch_current_stats_batch calls. The empty one is the Stale Deal Rescue, which
        finds nothing against the mocked DB and is skipped outright below 10/min, so
        filtering on emptiness keeps the assertions tier-independent. `started` maps each
        patched name to its mock.
        """
        patchers = {
            name: patch('keepa_deals.smart_ingestor.' + name)
            for name in ('redis.Redis', 'get_db_connection', 'TokenManager',
                         'fetch_deals_for_deals', 'fetch_current_stats_batch',
                         'fetch_product_batch', 'check_peek_viability',
                         'load_watermark', 'save_watermark',
                         'create_deals_table_if_not_exists',
                         'requeue_stuck_restrictions',
                         'get_seller_info_for_single_deal',
                         '_process_single_deal', 'celery')
        }
        started = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        # run() returns early at "KEEPA_API_KEY not set. Aborting." before reaching any
        # fetch. Pin the key so the test is hermetic rather than dependent on .env.
        env = patch.dict(os.environ, {'KEEPA_API_KEY': 'test_key_not_a_real_credential'})
        env.start()
        self.addCleanup(env.stop)

        started['load_watermark'].return_value = "2023-01-01T00:00:00+00:00"
        watermark_mins = smart_ingestor._convert_iso_to_keepa_time(
            "2023-01-01T00:00:00+00:00")
        deals = [{'asin': f'ASIN{i:06d}', 'lastUpdate': watermark_mins + 100 + i}
                 for i in range(deal_count)]

        def side_effect_fetch_deals(page, *args, **kwargs):
            return ({'deals': {'dr': deals if page == 0 else []}}, 0, deal_count)
        started['fetch_deals_for_deals'].side_effect = side_effect_fetch_deals

        mock_tm = started['TokenManager'].return_value
        type(mock_tm).REFILL_RATE_PER_MINUTE = unittest.mock.PropertyMock(
            return_value=refill_rate)
        mock_tm.should_skip_sync.return_value = False

        started['get_db_connection'].connect.return_value.cursor.return_value \
            .fetchall.return_value = []

        started['check_peek_viability'].return_value = True

        def side_effect_peek(api_key, asins, days, offers):
            return {'products': [{'asin': a, 'stats': {}} for a in asins]}, None, 0, 100
        started['fetch_current_stats_batch'].side_effect = side_effect_peek

        def side_effect_commit(api_key, asins, days=365, offers=20, rating=1, history=0):
            return {'products': [{'asin': a} for a in asins]}, None, 0, 100
        started['fetch_product_batch'].side_effect = side_effect_commit

        started['_process_single_deal'].return_value = {'ASIN': 'TEST', 'Title': 'Mock Title'}
        started['get_seller_info_for_single_deal'].return_value = {}

        smart_ingestor.run()

        peek_calls = [call
                      for call in started['fetch_current_stats_batch'].call_args_list
                      if call.args[1]]
        return peek_calls, started

    def test_peek_batch_size_scales_with_the_refill_rate(self):
        """Each tier, asserted separately so a failure names the tier that moved."""
        for refill_rate, expected in ((5, 1), (15, 20), (25, 15), (35, 50)):
            with self.subTest(refill_rate=refill_rate):
                peek_calls, _ = self._run_ingestor(refill_rate)
                self.assertTrue(
                    peek_calls,
                    f"no peek call was made at {refill_rate}/min")
                self.assertEqual(
                    expected, len(peek_calls[0].args[1]),
                    f"at {refill_rate} tokens/min the first peek batch should carry "
                    f"{expected} ASINs")

    def test_peek_offers_parameter_stays_at_20(self):
        """The peek is cheap because of offers=20; rate-scaling must not change it."""
        peek_calls, _ = self._run_ingestor(self.LIVE_REFILL_RATE)
        self.assertTrue(peek_calls)
        self.assertEqual(20, peek_calls[0].kwargs.get('offers'))

    def test_commit_batches_stay_at_five_and_every_deal_is_processed(self):
        """Commit sizing is NOT rate-scaled - COMMIT_BATCH_SIZE is a flat safety limit."""
        peek_calls, started = self._run_ingestor(
            self.LIVE_REFILL_RATE, deal_count=100)
        mock_fetch_product = started['fetch_product_batch']
        mock_process_single = started['_process_single_deal']

        self.assertEqual(
            100, sum(len(c.args[1]) for c in peek_calls),
            "every deal in the feed should be peeked exactly once")

        for index, call in enumerate(mock_fetch_product.call_args_list):
            self.assertLessEqual(
                len(call.args[1]), smart_ingestor.COMMIT_BATCH_SIZE,
                f"commit batch {index} exceeded COMMIT_BATCH_SIZE "
                f"({smart_ingestor.COMMIT_BATCH_SIZE})")

        self.assertEqual(
            100, mock_process_single.call_count,
            "every peeked deal that passed check_peek_viability should be processed")

    @patch('keepa_deals.smart_ingestor.redis.Redis')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    def test_recharge_exception_handling(self, mock_token_manager_cls, mock_redis):
        # Mock TokenManager to raise exception immediately
        mock_tm = mock_token_manager_cls.return_value
        type(mock_tm).REFILL_RATE_PER_MINUTE = unittest.mock.PropertyMock(return_value=20)
        mock_tm.request_permission_for_call.side_effect = TokenRechargeError("Test Recharge")
        # Ensure should_skip_sync is False so we proceed to request_permission
        mock_tm.should_skip_sync.return_value = False

        # Mock Redis lock
        mock_lock = MagicMock()
        mock_redis.from_url.return_value.lock.return_value = mock_lock
        mock_lock.acquire.return_value = True
        mock_lock.locked.return_value = True # Ensure release is called

        # Run
        smart_ingestor.run()

        # Verify lock released
        mock_lock.release.assert_called_once()
        print("Recharge Exception Test passed!")

    @patch('keepa_deals.smart_ingestor.redis.Redis')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    def test_skip_sync_logic(self, mock_token_manager_cls, mock_redis):
        # Mock TokenManager to indicate we should skip sync
        mock_tm = mock_token_manager_cls.return_value
        type(mock_tm).REFILL_RATE_PER_MINUTE = unittest.mock.PropertyMock(return_value=20)
        mock_tm.should_skip_sync.return_value = True
        # Also ensure request_permission eventually raises the error (since we are recharging)
        mock_tm.request_permission_for_call.side_effect = TokenRechargeError("Recharge needed")

        # Mock Redis lock
        mock_lock = MagicMock()
        mock_redis.from_url.return_value.lock.return_value = mock_lock
        mock_lock.acquire.return_value = True
        mock_lock.locked.return_value = True

        # Run
        smart_ingestor.run()

        # Assert sync_tokens was NOT called
        mock_tm.sync_tokens.assert_not_called()

        # Assert lock released
        mock_lock.release.assert_called_once()

        print("Skip Sync Test passed!")

if __name__ == '__main__':
    unittest.main()
