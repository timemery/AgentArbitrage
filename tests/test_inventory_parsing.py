
import unittest
import io
import csv
import sys
import os
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.inventory_import import parse_inventory_report_content, REPORT_TYPE_FBA, REPORT_TYPE_MERCHANT

# Sample FBA Report Data (Tab-separated)
# Based on Amazon documentation for GET_FBA_MYI_ALL_INVENTORY_DATA (Format is identical for columns used)
SAMPLE_FBA_REPORT = """sku\tfnsku\tasin\tproduct-name\tcondition\tyour-price\tmfn-listing-exists\tmfn-fulfillable-quantity\tafn-listing-exists\tafn-warehouse-quantity\tafn-fulfillable-quantity\tafn-unsellable-quantity\tafn-reserved-quantity\tafn-total-quantity\tafn-inbound-working-quantity\tafn-inbound-shipped-quantity\tafn-inbound-receiving-quantity
SKU-123\tFNSKU1\tASIN123\tTest Product 1\tNew\t19.99\tNo\t0\tYes\t10\t5\t0\t0\t5\t2\t3\t0
SKU-456\tFNSKU2\tASIN456\tTest Product 2\tUsed\t15.00\tNo\t0\tYes\t0\t0\t0\t0\t0\t10\t0\t5
SKU-789\tFNSKU3\tASIN789\tTest Product 3\tNew\t25.00\tNo\t0\tYes\t0\t\t0\t0\t0\t\t\t
"""
# Note: SKU-789 has empty strings for quantities to test safe_int

# Sample Merchant Report Data
SAMPLE_MERCHANT_REPORT = """seller-sku\tasin1\titem-name\tprice\tquantity\tfulfillment-channel
SKU-MFN\tASIN_MFN\tMerchant Product\t25.00\t50\tDEFAULT
SKU-FBA\tASIN_FBA\tTest Product 1\t19.99\t0\tAMAZON_NA
"""

class TestInventoryParsing(unittest.TestCase):
    def test_parse_fba_report(self):
        items = parse_inventory_report_content(SAMPLE_FBA_REPORT, REPORT_TYPE_FBA)

        # Check SKU-123
        # Fulfillable: 5, Inbound Working: 2, Shipped: 3, Receiving: 0 => Total 10
        item1 = next(i for i in items if i['sku'] == 'SKU-123')
        self.assertEqual(item1['quantity'], 10)
        self.assertTrue(item1['is_fba'])

        # Check SKU-456
        # Fulfillable: 0, Inbound Working: 10, Shipped: 0, Receiving: 5 => Total 15
        item2 = next(i for i in items if i['sku'] == 'SKU-456')
        self.assertEqual(item2['quantity'], 15)

        # Check SKU-789 (Empty strings)
        # Should be treated as 0
        item3 = next(i for i in items if i['sku'] == 'SKU-789')
        self.assertEqual(item3['quantity'], 0)

    def test_parse_merchant_report(self):
        items = parse_inventory_report_content(SAMPLE_MERCHANT_REPORT, REPORT_TYPE_MERCHANT)

        # Check SKU-MFN (MFN)
        item1 = next(i for i in items if i['sku'] == 'SKU-MFN')
        self.assertEqual(item1['quantity'], 50)
        self.assertFalse(item1['is_fba'])

        # Check SKU-FBA (FBA in Merchant Report)
        item2 = next(i for i in items if i['sku'] == 'SKU-FBA')
        self.assertEqual(item2['quantity'], 0)
        self.assertTrue(item2['is_fba'])

if __name__ == '__main__':
    unittest.main()
