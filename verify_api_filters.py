
import requests
import json
import sqlite3
import os
import unittest
from wsgi_handler import app

class TestAPIFilters(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.db_path = os.getenv("DATABASE_URL", "/app/deals.db")

        # Insert a dummy deal to test filtering if the DB is empty
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if table exists, if not create it (simplified for testing)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deals'")
        if not cursor.fetchone():
            # Minimal schema for testing
            cursor.execute('''CREATE TABLE deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ASIN TEXT UNIQUE,
                Title TEXT,
                Sales_Rank_Current INTEGER,
                Margin REAL,
                Profit_Confidence INTEGER,
                Seller_Quality_Score REAL,
                Profit REAL,
                Percent_Down INTEGER
            )''')

        # Insert test data
        try:
            cursor.execute('''INSERT OR REPLACE INTO deals
                (ASIN, Title, Sales_Rank_Current, Margin, Profit_Confidence, Seller_Quality_Score, Profit, Percent_Down)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                ('TEST123456', 'Test Book', 1000, 20.0, 80, 4.5, 10.0, 15)
            )
            conn.commit()
        except Exception as e:
            print(f"Error inserting test data: {e}")

        conn.close()

    def test_filter_profit_confidence(self):
        response = self.client.get('/api/deals?profit_confidence_gte=50')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('deals', data)
        # Should find at least the test deal
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertTrue(found, "Should find deal with Profit Confidence 80 when filtering >= 50")

        response = self.client.get('/api/deals?profit_confidence_gte=90')
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertFalse(found, "Should NOT find deal with Profit Confidence 80 when filtering >= 90")

    def test_filter_seller_trust(self):
        # 4.5 score corresponds to 90% (4.5 / 5 * 100)
        # Filter >= 80% (4.0) should match
        response = self.client.get('/api/deals?seller_trust_gte=80')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertTrue(found, "Should find deal with Seller Trust 4.5 when filtering >= 80%")

        # Filter >= 95% (4.75) should not match
        response = self.client.get('/api/deals?seller_trust_gte=95')
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertFalse(found, "Should NOT find deal with Seller Trust 4.5 when filtering >= 95%")

    def test_filter_profit(self):
        response = self.client.get('/api/deals?profit_gte=5')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertTrue(found, "Should find deal with Profit 10 when filtering >= 5")

        response = self.client.get('/api/deals?profit_gte=20')
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertFalse(found, "Should NOT find deal with Profit 10 when filtering >= 20")

    def test_filter_percent_down(self):
        response = self.client.get('/api/deals?percent_down_gte=10')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertTrue(found, "Should find deal with Percent Down 15 when filtering >= 10")

        response = self.client.get('/api/deals?percent_down_gte=20')
        data = json.loads(response.data)
        found = any(d.get('ASIN') == 'TEST123456' for d in data['deals'])
        self.assertFalse(found, "Should NOT find deal with Percent Down 15 when filtering >= 20")

if __name__ == '__main__':
    unittest.main()
