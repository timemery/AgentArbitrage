"""The Keepa API key must not reach a log by ANY path - Trello #145.

`test_keepa_api_key_redaction.py` pins `redact()` on the error lines that call it.
Three paths reached the log without passing through one:

  1.  A traceback. `logger.error(f"...{redact(e)}", exc_info=True)` redacts the
      message, then `logging` renders the exception text itself, unredacted. A
      `requests` exception's text carries the full URL, key included.
  2.  `logger.debug(f"Deal URL: {url}")` in `stable_deals.py`.
  3.  urllib3's own DEBUG line for every request (`"GET /product?key=..."`), which
      `wsgi_handler.py` writes to `app.log`: it runs the root logger at DEBUG and
      `/api/product/<asin>` fetches from Keepa in the web process.

`keepa_api` now wraps the logging record factory, so every record is redacted
where it is created. Also pinned here: the seller fetcher no longer sends the
literal seller id "Unknown" to Keepa, and no longer feeds a None token count to
`update_after_call`.
"""

import io
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals import keepa_api  # noqa: E402
from keepa_deals import seller_info  # noqa: E402

FAKE_KEY = 'a' * 20 + '0123456789abcdefSECRETKEY0123456789'


class _Captured:
    """A logger with its own handler, the way Celery or Apache would attach one."""

    def __init__(self, name):
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
        self.logger = logging.getLogger(name)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

    def text(self):
        self.handler.flush()
        return self.stream.getvalue()

    def close(self):
        self.logger.removeHandler(self.handler)


class EveryRecordIsRedacted(unittest.TestCase):

    def setUp(self):
        self.cap = _Captured('test_keepa_log_redaction_net')

    def tearDown(self):
        self.cap.close()

    def test_a_traceback_loses_the_key(self):
        try:
            raise ConnectionError(
                'Max retries exceeded with url: /seller?key={}&domain=1'.format(FAKE_KEY))
        except ConnectionError:
            self.cap.logger.error('fetch failed', exc_info=True)
        out = self.cap.text()
        self.assertIn('Traceback', out)
        self.assertIn('key=<REDACTED>&domain=1', out)
        self.assertNotIn(FAKE_KEY, out)

    def test_a_debug_url_loses_the_key(self):
        self.cap.logger.debug('Deal URL: https://api.keepa.com/deal?key=%s&selection=x', FAKE_KEY)
        out = self.cap.text()
        self.assertIn('key=<REDACTED>&selection=x', out)
        self.assertNotIn(FAKE_KEY, out)

    def test_a_urllib3_request_line_loses_the_key(self):
        # urllib3.connectionpool's own format string.
        self.cap.logger.debug('%s://%s:%s "%s %s %s" %s %s', 'https', 'api.keepa.com', 443,
                              'GET', '/product?key={}&domain=1'.format(FAKE_KEY),
                              'HTTP/1.1', 200, None)
        out = self.cap.text()
        self.assertNotIn(FAKE_KEY, out)
        self.assertIn('/product?key=<REDACTED>&domain=1', out)

    def test_a_short_lookup_key_stays_readable(self):
        """stable_products.py logs `key=current, index=2`; that is not a secret."""
        self.cap.logger.warning('get_stat_value: No data for key=current, index=2')
        self.assertIn('key=current, index=2', self.cap.text())

    def test_a_line_without_a_key_is_untouched(self):
        self.cap.logger.info('Tokens left: %s', 280)
        self.assertIn('Tokens left: 280', self.cap.text())


class TheHookIsInstalledOnce(unittest.TestCase):

    def test_importing_keepa_api_installs_it(self):
        self.assertTrue(getattr(logging.getLogRecordFactory(), '_keepa_key_redaction', False))

    def test_installing_again_does_not_stack(self):
        before = logging.getLogRecordFactory()
        keepa_api.install_log_redaction()
        self.assertIs(logging.getLogRecordFactory(), before)


class TheSellerFetcherSkipsUnknown(unittest.TestCase):

    def _run(self, seller_id, fetch_result):
        token_manager = MagicMock()
        with patch.object(seller_info, 'get_used_product_info',
                          return_value=(1000, seller_id, False, 2)), \
             patch.object(seller_info, 'fetch_seller_data',
                          return_value=fetch_result) as fetch:
            result = seller_info.get_seller_info_for_single_deal(
                {'asin': '0000000000'}, 'k', token_manager)
        return result, fetch, token_manager

    def test_unknown_is_never_sent_to_keepa(self):
        result, fetch, token_manager = self._run('Unknown', (None, {}, 0, None))
        self.assertEqual(result, {})
        fetch.assert_not_called()
        token_manager.request_permission_for_call.assert_not_called()

    def test_a_real_seller_is_still_fetched(self):
        data = {'sellers': {'A1B2C3': {'sellerName': 'Shop'}}}
        result, fetch, token_manager = self._run('A1B2C3', (data, {}, 1, 279))
        fetch.assert_called_once_with('k', ['A1B2C3'])
        token_manager.update_after_call.assert_called_once_with(279)
        self.assertEqual(result, data['sellers'])

    def test_a_missing_token_count_is_not_fed_to_the_token_manager(self):
        _, _, token_manager = self._run('A1B2C3', (None, {'error_status_code': 500}, 0, None))
        token_manager.update_after_call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
