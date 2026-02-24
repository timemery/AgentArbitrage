import unittest
import sqlite3
import os
import json
import tempfile
from datetime import datetime, timedelta
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wsgi_handler import app, DB_PATH
from keepa_deals.db_utils import create_inventory_ledger_table_if_not_exists, create_sales_ledger_table_if_not_exists

class TestTrackingPagination(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = app.test_client()
        self.app.testing = True

        # Patch DB_PATH in wsgi_handler (and db_utils if needed, but wsgi imports it)
        # Actually, wsgi_handler imports DB_PATH from db_utils.
        # So we need to patch keepa_deals.db_utils.DB_PATH
        import keepa_deals.db_utils
        keepa_deals.db_utils.DB_PATH = self.db_path
        # Also patch wsgi_handler.DB_PATH which was imported
        import wsgi_handler
        wsgi_handler.DB_PATH = self.db_path

        # Initialize Tables
        create_inventory_ledger_table_if_not_exists()
        create_sales_ledger_table_if_not_exists()

        # Seed Data
        self.seed_data()

        # Login
        with self.app.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'tester'

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def seed_data(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Seed 60 Active Inventory Items
            for i in range(60):
                cursor.execute("""
                    INSERT INTO inventory_ledger (asin, title, sku, purchase_date, buy_cost, quantity_purchased, quantity_remaining, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'PURCHASED')
                """, (f'ASIN{i}', f'Book Title {i}', f'SKU{i}', datetime.now().isoformat(), 10.00, 1, 1))

            # Seed 60 Sales
            for i in range(60):
                cursor.execute("""
                    INSERT INTO sales_ledger (amazon_order_id, order_item_id, asin, sku, sale_date, sale_price, quantity_sold, order_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Shipped')
                """, (f'ORDER{i}', f'ITEM{i}', f'ASIN{i}', f'SKU{i}', datetime.now().isoformat(), 20.00, 1))

            conn.commit()

    def test_active_inventory_pagination(self):
        # Page 1
        response = self.app.get('/api/tracking/active?page=1&limit=50')
        data = json.loads(response.data)

        self.assertEqual(len(data['data']), 50)
        self.assertEqual(data['pagination']['total'], 60)
        self.assertEqual(data['pagination']['page'], 1)
        self.assertEqual(data['pagination']['pages'], 2)

        # Page 2
        response = self.app.get('/api/tracking/active?page=2&limit=50')
        data = json.loads(response.data)

        self.assertEqual(len(data['data']), 10)
        self.assertEqual(data['pagination']['page'], 2)

    def test_sales_history_pagination(self):
        # Page 1
        response = self.app.get('/api/tracking/sales?page=1&limit=50')
        data = json.loads(response.data)

        self.assertEqual(len(data['data']), 50)
        self.assertEqual(data['pagination']['total'], 60)

        # Page 2
        response = self.app.get('/api/tracking/sales?page=2&limit=50')
        data = json.loads(response.data)

        self.assertEqual(len(data['data']), 10)

if __name__ == '__main__':
    unittest.main()
