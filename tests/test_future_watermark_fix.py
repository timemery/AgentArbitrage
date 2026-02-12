import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.smart_ingestor import save_safe_watermark

class TestFutureWatermarkFix(unittest.TestCase):

    @patch('keepa_deals.smart_ingestor.save_watermark')
    @patch('keepa_deals.smart_ingestor.datetime')
    def test_save_safe_watermark_clamping(self, mock_datetime, mock_save_watermark):
        # Setup specific "now"
        fixed_now = datetime(2026, 2, 12, 14, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.combine = datetime.combine

        # Case 1: Past timestamp (Should be saved as is)
        past_iso = "2026-02-12T13:55:00+00:00"
        save_safe_watermark(past_iso)
        mock_save_watermark.assert_called_with(past_iso)

        # Case 2: Small Future timestamp (5 mins) - Should be ALLOWED (Fix)
        # Previously clamped to now.
        future_small_iso = "2026-02-12T14:05:00+00:00"
        save_safe_watermark(future_small_iso)
        # We expect it to be SAVED AS IS to prevent loops.
        # If the code clamps, this assertion will fail (which is what we want to verify before fixing)
        # For now, let's assert the DESIRED behavior.
        mock_save_watermark.assert_called_with(future_small_iso)

        # Case 3: Large Future timestamp (> 24 hours) - Should be CLAMPED
        future_large_iso = "2026-02-13T15:00:00+00:00" # 25 hours ahead
        save_safe_watermark(future_large_iso)
        # Expect clamping to now
        mock_save_watermark.assert_called_with(fixed_now.isoformat())

if __name__ == '__main__':
    unittest.main()
