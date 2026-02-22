
import unittest
import sqlite3
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add parent directory to path to import keepa_deals
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from keepa_deals.inventory_import import _download_and_process_report, REPORT_TYPE_MERCHANT, REPORT_TYPE_FBA
from keepa_deals.db_utils import DB_PATH, create_inventory_ledger_table_if_not_exists

class TestInventoryImport(unittest.TestCase):
    def setUp(self):
        # Use an in-memory database for testing or a temp file
        self.db_path = 'test_deals.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        # Patch DB_PATH in db_utils (this is tricky because it's imported)
        self.patcher = patch('keepa_deals.inventory_import.DB_PATH', self.db_path)
        self.mock_db_path = self.patcher.start()

        # Also patch DB_PATH in db_utils if used there
        self.patcher2 = patch('keepa_deals.db_utils.DB_PATH', self.db_path)
        self.mock_db_path2 = self.patcher2.start()

        # Initialize DB
        create_inventory_ledger_table_if_not_exists()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_merchant_and_fba_report_sync(self):
        # 1. Process Merchant Report (FBA Qty 0)
        merchant_report_content = (
            "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\timage-url\titem-is-marketplace\tproduct-id-type\tzshop-shipping-fee\titem-note\titem-condition\tzshop-category1\tzshop-browse-path\tzshop-storefront-feature\tasin1\toption-payment-type\tgeneric-keywords\titem-is-merchant-shipping\tfulfillment-channel\tzshop-boldface\tproduct-id\tmerchant-shipping-group-name\tprogress-type\n"
            "FBA Item\tDesc\t123\tFBA_SKU\t10.00\t0\t2023-01-01\t\ty\t1\t0.00\t\t11\t\t\t0\tASIN_FBA\t\tkw\tn\tAMAZON_NA\t\tASIN_FBA\tLegacy-Template\t\n"
            "MFN Item\tDesc\t124\tMFN_SKU\t10.00\t5\t2023-01-01\t\ty\t1\t3.99\t\t11\t\t\t0\tASIN_MFN\t\tkw\ty\tDEFAULT\t\tASIN_MFN\tMigrated Template\t\n"
        ).encode('utf-8')

        with patch('keepa_deals.inventory_import.requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = merchant_report_content
            _download_and_process_report('http://mock.url/merchant', None, 'user123', REPORT_TYPE_MERCHANT)

        # Check DB State 1
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check FBA SKU (should be 0)
            cursor.execute("SELECT quantity_remaining FROM inventory_ledger WHERE sku = 'FBA_SKU'")
            fba_qty = cursor.fetchone()[0]
            self.assertEqual(fba_qty, 0, "FBA Item should have 0 qty after Merchant Report")

            # Check MFN SKU (should be 5)
            cursor.execute("SELECT quantity_remaining FROM inventory_ledger WHERE sku = 'MFN_SKU'")
            mfn_qty = cursor.fetchone()[0]
            self.assertEqual(mfn_qty, 5, "MFN Item should have 5 qty")

        # 2. Process FBA Report (FBA Qty 10)
        fba_report_content = (
            "sku\tfnsku\tasin\tproduct-name\tcondition\tyour-price\tmfn-listing-exists\tmfn-fulfillable-quantity\tafn-listing-exists\tafn-warehouse-quantity\tafn-fulfillable-quantity\tafn-unsellable-quantity\tafn-reserved-quantity\tafn-total-quantity\tper-unit-volume\tafn-inbound-working-quantity\tafn-inbound-shipped-quantity\tafn-inbound-receiving-quantity\tafn-researching-quantity\tafn-reserved-future-supply\tafn-future-supply-buyable\n"
            "FBA_SKU\tFNSKU1\tASIN_FBA\tFBA Item\t11\t10.00\t\t0\ty\t10\t10\t0\t0\t10\t0.0\t0\t0\t0\t0\t0\t0\n"
        ).encode('utf-8')

        with patch('keepa_deals.inventory_import.requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = fba_report_content
            _download_and_process_report('http://mock.url/fba', None, 'user123', REPORT_TYPE_FBA)

        # Check DB State 2
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check FBA SKU (should be updated to 10)
            cursor.execute("SELECT quantity_remaining FROM inventory_ledger WHERE sku = 'FBA_SKU'")
            fba_qty = cursor.fetchone()[0]
            self.assertEqual(fba_qty, 10, "FBA Item should have 10 qty after FBA Report")

            # Check MFN SKU (should remain 5)
            cursor.execute("SELECT quantity_remaining FROM inventory_ledger WHERE sku = 'MFN_SKU'")
            mfn_qty = cursor.fetchone()[0]
            self.assertEqual(mfn_qty, 5, "MFN Item should remain 5 qty")

if __name__ == '__main__':
    unittest.main()
