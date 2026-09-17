"""The Keepa API key must never reach a log.

WHY THIS FILE EXISTS
--------------------
Found in production logs on 2026-09-17, during the #139 pricing-repair dry run:

    HTTP fetch failed for seller batch with status 400: ...
    url: https://api.keepa.com/seller?key=<THE REAL KEY>&seller=Unknown

`requests` puts the full request URL into its exception's string form, and every
fetcher in `keepa_api.py` interpolated `{e}` or `{str(e)}` straight into a
`logger.error`. Every Keepa URL in that module carries `key=<API key>` as a query
parameter, so ANY HTTP error published the key into `celery_worker.log` - which is
world-readable on the box, gets copied around when debugging, and is the first
thing pasted into a bug report.

WHAT IS PINNED HERE
-------------------
  1.  `redact()` removes the key from any text, by pattern - not by comparing
      against the configured key, so a stale key, an explicitly passed key or a
      second account's key are all covered.
  2.  It leaves everything else in the message intact. A redaction that ate the
      status code or the ASIN list would get reverted the first time somebody
      needed to debug a 429.
  3.  EVERY error path in the module redacts, not just the seller fetcher that
      happened to be the one caught. Asserted against the module source, because
      a behavioural test can only reach the paths it can provoke.

These tests FAIL on the parent commit (fce3745), where `redact` does not exist.
"""

import logging
import os
import re
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests  # noqa: E402

from keepa_deals import keepa_api  # noqa: E402
from keepa_deals.keepa_api import redact  # noqa: E402

FAKE_KEY = 'sk-live-0123456789abcdefSECRET'


class RedactRemovesTheKey(unittest.TestCase):

    def test_a_seller_url_loses_its_key(self):
        text = ('url: https://api.keepa.com/seller?key={}&domain=1&seller=Unknown'
                .format(FAKE_KEY))
        out = redact(text)
        self.assertNotIn(FAKE_KEY, out)
        self.assertIn('<REDACTED>', out)

    def test_every_keepa_endpoint_url_is_covered(self):
        """All five URL builders in the module embed the key the same way."""
        for url in (
            'https://api.keepa.com/token?key={}'.format(FAKE_KEY),
            'https://api.keepa.com/deal?key={}&selection=%7B%7D'.format(FAKE_KEY),
            'https://api.keepa.com/product?key={}&domain=1&asin=B01'.format(FAKE_KEY),
            'https://api.keepa.com/seller?key={}&domain=1&seller=X'.format(FAKE_KEY),
        ):
            self.assertNotIn(FAKE_KEY, redact(url), url)

    def test_the_rest_of_the_message_survives(self):
        """A redaction that ate the diagnostics would be reverted on first use."""
        text = ('HTTP fetch failed for seller batch with status 400: 400 Client '
                'Error for url: https://api.keepa.com/seller?key={}&seller=Unknown'
                .format(FAKE_KEY))
        out = redact(text)
        self.assertIn('status 400', out)
        self.assertIn('seller=Unknown', out)
        self.assertIn('api.keepa.com/seller', out)

    def test_it_redacts_by_pattern_not_by_matching_the_configured_key(self):
        """A stale or foreign key must be caught too."""
        with patch.dict(os.environ, {'KEEPA_API_KEY': 'a-completely-different-key'}):
            self.assertNotIn('someOtherAccountKey',
                             redact('?key=someOtherAccountKey&x=1'))

    def test_common_spellings_are_covered(self):
        for param in ('key', 'KEY', 'api_key', 'apikey'):
            self.assertNotIn(FAKE_KEY,
                             redact('?{}={}&z=1'.format(param, FAKE_KEY)), param)

    def test_it_stops_at_the_parameter_boundary(self):
        out = redact('?key={}&seller=Unknown&domain=1'.format(FAKE_KEY))
        self.assertIn('&seller=Unknown', out)
        self.assertIn('&domain=1', out)

    def test_none_and_empty_are_passed_through(self):
        self.assertIsNone(redact(None))
        self.assertEqual(redact(''), '')

    def test_text_without_a_key_is_unchanged(self):
        text = 'Fetched 50 deals. Tokens consumed: 12. Tokens left: 88.'
        self.assertEqual(redact(text), text)


class EveryErrorPathRedacts(unittest.TestCase):
    """Source-level, because a behavioural test reaches only what it can provoke.

    The leak was in ONE of ten error logs. Fixing that one and calling it done is
    how the next fetcher republishes the key.
    """

    def test_no_error_log_interpolates_a_raw_exception(self):
        source = open(keepa_api.__file__, encoding='utf-8').read()
        offenders = []
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#') or 'logger.' not in stripped:
                continue
            if re.search(r'\{(?:str\()?e\)?\}', stripped) and 'redact(' not in stripped:
                offenders.append('{}: {}'.format(i, stripped))
            if 'e.response.text' in stripped and 'redact(' not in stripped:
                offenders.append('{}: {}'.format(i, stripped))
        self.assertEqual(
            offenders, [],
            "These log lines can carry the request URL - and every Keepa URL "
            "carries key=<API key>:\n  " + "\n  ".join(offenders))

    def test_the_reason_is_recorded_next_to_the_code(self):
        """Per AGENTS.md 6.2 - a bare `redact()` reads like paranoia."""
        self.assertIn('key=<THE REAL KEY>', redact.__doc__ or '')
        self.assertIn('Rotate the key', redact.__doc__ or '')


class TheSellerFetcherDoesNotLeak(unittest.TestCase):
    """The exact call that leaked, driven end to end with the network stubbed."""

    def setUp(self):
        self.records = []

        class _Capture(logging.Handler):
            def emit(_self, record):
                self.records.append(record.getMessage())

        self.handler = _Capture()
        logging.getLogger('keepa_deals.keepa_api').addHandler(self.handler)
        logging.getLogger('keepa_deals.keepa_api').setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger('keepa_deals.keepa_api').removeHandler(self.handler)

    def test_a_400_on_the_seller_endpoint_logs_no_key(self):
        response = requests.Response()
        response.status_code = 400
        response._content = b'not json'
        error = requests.exceptions.HTTPError(
            "400 Client Error: Bad Request for url: "
            "https://api.keepa.com/seller?key={}&domain=1&seller=Unknown"
            .format(FAKE_KEY),
            response=response)

        with patch.object(keepa_api.requests, 'get', side_effect=error):
            keepa_api.fetch_seller_data(FAKE_KEY, ['Unknown'])

        joined = '\n'.join(self.records)
        self.assertTrue(joined, "Nothing was logged; the test proved nothing.")
        self.assertNotIn(FAKE_KEY, joined,
                         "The API key reached the log:\n" + joined)
        self.assertIn('status 400', joined,
                      "The diagnostic content must survive redaction.")


if __name__ == '__main__':
    unittest.main()
