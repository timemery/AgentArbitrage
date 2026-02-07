import unittest
import sqlite3
import os
import json
from wsgi_handler import app

# Create a temporary DB
TEST_DB = 'test_deals.db'

class TestApiFiltering(unittest.TestCase):
    def setUp(self):
        # Create a fresh DB with the correct schema
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

        conn = sqlite3.connect(TEST_DB)
        cursor = conn.cursor()

        # Schema from check_schema.py but simplified for relevant columns
        cursor.execute("""
            CREATE TABLE deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ASIN TEXT UNIQUE,
                Title TEXT,
                Profit REAL,
                List_at REAL,
                "1yr_Avg" TEXT,  -- Note: Still TEXT in production schema
                Percent_Down TEXT,
                Seller_Quality_Score TEXT,
                Margin REAL,
                Sales_Rank_Current INTEGER,
                Profit_Confidence REAL,
                AMZ TEXT
            )
        """)

        # Insert test data
        deals = [
            # Good Deal
            ('GOOD001', 'Good Book', 10.0, 50.0, '40.0', '20', '0.9', 20.0, 50000, 80.0, None),
            # Bad Profit (Zero)
            ('BAD001', 'Zero Profit', 0.0, 50.0, '40.0', '0', '0.9', 0.0, 50000, 80.0, None),
            # Bad Profit (Negative)
            ('BAD002', 'Negative Profit', -5.0, 50.0, '40.0', '0', '0.9', -10.0, 50000, 80.0, None),
            # Missing List_at (NULL)
            ('BAD003', 'No List Price', 10.0, None, '40.0', '20', '0.9', 20.0, 50000, 80.0, None),
            # Missing List_at (Zero)
            ('BAD004', 'Zero List Price', 10.0, 0.0, '40.0', '20', '0.9', 20.0, 50000, 80.0, None),
            # Missing 1yr Avg (Placeholder)
            ('BAD005', 'No Avg', 10.0, 50.0, '-', '20', '0.9', 20.0, 50000, 80.0, None),
            # Missing 1yr Avg (Zero string)
            ('BAD006', 'Zero Avg String', 10.0, 50.0, '0', '20', '0.9', 20.0, 50000, 80.0, None),
             # Missing 1yr Avg (Zero number check)
            ('BAD007', 'Zero Avg Num', 10.0, 50.0, '0.00', '20', '0.9', 20.0, 50000, 80.0, None),
        ]

        cursor.executemany("""
            INSERT INTO deals (ASIN, Title, Profit, List_at, "1yr_Avg", Percent_Down, Seller_Quality_Score, Margin, Sales_Rank_Current, Profit_Confidence, AMZ)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, deals)

        conn.commit()
        conn.close()

        # Point the app to the test DB
        # We need to mock the DATABASE_URL in the app context or modify it directly
        # Since wsgi_handler.py uses a global variable DATABASE_URL, we might need to patch it
        # However, api_deals re-reads it from os.getenv or the global.
        # Let's set the env var for the process? No, python reads it once.
        # But `api_deals` function has `DB_PATH = DATABASE_URL` inside it? No, it uses the global.
        # Wait, let's check `api_deals` source again.
        # It says `DB_PATH = DATABASE_URL` at the start of the function.
        # And `DATABASE_URL` is defined at module level.
        # We can monkeypatch `wsgi_handler.DATABASE_URL`.

        import wsgi_handler
        wsgi_handler.DATABASE_URL = TEST_DB

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_api_deals_filtering(self):
        with app.test_client() as client:
            # Login first (mock session)
            with client.session_transaction() as sess:
                sess['logged_in'] = True

            # Request all deals (default filters)
            response = client.get('/api/deals')
            data = json.loads(response.data)

            deals = data['deals']
            asins = [d['ASIN'] for d in deals]

            # Verify ONLY the good deal is returned
            self.assertIn('GOOD001', asins)
            self.assertNotIn('BAD001', asins, "Zero Profit should be filtered")
            self.assertNotIn('BAD002', asins, "Negative Profit should be filtered")
            self.assertNotIn('BAD003', asins, "NULL List_at should be filtered")
            self.assertNotIn('BAD004', asins, "Zero List_at should be filtered")
            self.assertNotIn('BAD005', asins, "Hyphen Avg should be filtered")
            self.assertNotIn('BAD006', asins, "Zero string Avg should be filtered")
            self.assertNotIn('BAD007', asins, "Zero number string Avg should be filtered")

if __name__ == '__main__':
    unittest.main()
