import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.amazon_sp_api import check_restrictions

class TestSPAPIUrl(unittest.TestCase):
    @patch('keepa_deals.amazon_sp_api.requests.Session')
    def test_fallback_url(self, mock_session_cls):
        """Test that fallback URL uses the correct /hz/approvalrequest format."""
        mock_session = mock_session_cls.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Return restriction but NO links
        mock_response.json.return_value = {
            "restrictions": [
                {
                    "marketplaceId": "ATVPDKIKX0DER",
                    "conditionType": "new_new",
                    "reasons": [{"reasonCode": "APPROVAL_REQUIRED", "message": "Restricted"}],
                    "links": []
                }
            ]
        }
        mock_session.get.return_value = mock_response

        results = check_restrictions(['B123456789'], 'fake_token', 'fake_seller_id')

        # This expects the "Add a Product" search format
        expected_url = "https://sellercentral.amazon.com/product-search/search?q=B123456789"
        self.assertEqual(results['B123456789']['approval_url'], expected_url)

    @patch('keepa_deals.amazon_sp_api.requests.Session')
    def test_links_parsing_standard_list(self, mock_session_cls):
        """Test parsing of standard SP-API 'links' list (no 'actions' key)."""
        mock_session = mock_session_cls.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "restrictions": [
                {
                    "marketplaceId": "ATVPDKIKX0DER",
                    "links": [
                        {
                            "resource": "https://sellercentral.amazon.com/hz/approvalrequest/restrictions/approve?asin=B123456789",
                            "verb": "GET",
                            "title": "Request Approval"
                        }
                    ]
                }
            ]
        }
        mock_session.get.return_value = mock_response

        results = check_restrictions(['B123456789'], 'fake_token', 'fake_seller_id')

        expected_url = "https://sellercentral.amazon.com/hz/approvalrequest/restrictions/approve?asin=B123456789"
        self.assertEqual(results['B123456789']['approval_url'], expected_url)

if __name__ == '__main__':
    unittest.main()
