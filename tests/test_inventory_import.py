
import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.inventory_import import fetch_existing_inventory_task, process_bulk_cost_upload
from keepa_deals.db_utils import DB_PATH, create_deals_table_if_not_exists

class TestInventoryImport(unittest.TestCase):

    def setUp(self):
        # Initialize DB
        create_deals_table_if_not_exists()
        # Clear inventory ledger
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM inventory_ledger")
            conn.commit()

    @patch('keepa_deals.inventory_import.get_all_user_credentials')
    @patch('keepa_deals.inventory_import.refresh_sp_api_token')
    @patch('keepa_deals.inventory_import.requests')
    def test_fetch_existing_inventory_task(self, mock_requests, mock_refresh, mock_get_creds):
        # Mock credentials
        mock_get_creds.return_value = [{'user_id': 'test_user', 'refresh_token': 'test_refresh'}]
        mock_refresh.return_value = 'test_access_token'

        # Mock Request Report
        mock_resp_request = MagicMock()
        mock_resp_request.status_code = 202
        mock_resp_request.json.return_value = {'reportId': '123'}

        # Mock Poll Status
        mock_resp_poll = MagicMock()
        mock_resp_poll.status_code = 200
        mock_resp_poll.json.return_value = {'processingStatus': 'DONE', 'reportDocumentId': 'doc_123'}

        # Mock Get Document URL
        mock_resp_doc = MagicMock()
        mock_resp_doc.status_code = 200
        mock_resp_doc.json.return_value = {'url': 'http://mock.url', 'compressionAlgorithm': None}

        # Mock Download Report
        mock_resp_download = MagicMock()
        mock_resp_download.status_code = 200
        # TSV Content
        tsv_content = "seller-sku\tasin1\titem-name\tquantity\nSKU_A\tASIN_A\tTitle A\t10\nSKU_B\tASIN_B\tTitle B\t0"
        mock_resp_download.content = tsv_content.encode('utf-8')

        # Side effect for requests.post and get
        def side_effect(url, **kwargs):
            if 'reports' in url and 'documents' not in url:
                if kwargs.get('json'): # POST request
                    return mock_resp_request
                else: # Poll request
                    return mock_resp_poll
            elif 'documents' in url:
                return mock_resp_doc
            else: # Download
                return mock_resp_download

        mock_requests.post.side_effect = lambda url, **kwargs: mock_resp_request
        mock_requests.get.side_effect = side_effect

        # Run task
        fetch_existing_inventory_task()

        # Verify DB
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sku, asin, quantity_remaining FROM inventory_ledger ORDER BY sku")
            rows = cursor.fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], 'SKU_A')
        self.assertEqual(rows[0][1], 'ASIN_A')
        self.assertEqual(rows[0][2], 10)
        self.assertEqual(rows[1][0], 'SKU_B')
        self.assertEqual(rows[1][2], 0)

    def test_process_bulk_cost_upload(self):
        # Insert initial data
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO inventory_ledger (sku, asin, title) VALUES ('SKU_X', 'ASIN_X', 'Title X')")
            conn.commit()

        csv_content = "SKU,Buy Cost,Purchase Date\nSKU_X,15.50,2023-01-01"

        process_bulk_cost_upload(csv_content)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT buy_cost, purchase_date FROM inventory_ledger WHERE sku = 'SKU_X'")
            row = cursor.fetchone()

        self.assertEqual(row[0], 15.50)
        self.assertEqual(row[1], '2023-01-01')

if __name__ == '__main__':
    unittest.main()
