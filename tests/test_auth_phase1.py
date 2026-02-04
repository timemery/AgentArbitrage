import unittest
import sys
import os

# Add repo root to path to ensure wsgi_handler can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from wsgi_handler import app, USERS

class TestAuthPhase1(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test'
        self.client = app.test_client()

    def test_login_admin(self):
        response = self.client.post('/login', data={
            'username': 'tester',
            'password': USERS['tester']['password']
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Should redirect to Dashboard (UPDATED)
        self.assertTrue(b"Deals Dashboard" in response.data or b"Dashboard" in response.data)
        self.assertIn(b'id="deals-table"', response.data)

    def test_login_user(self):
        response = self.client.post('/login', data={
            'username': 'AristotleLogic',
            'password': USERS['AristotleLogic']['password']
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Check that "Strategies" link is NOT present
        self.assertNotIn(b'href="/strategies"', response.data)
        # Data Sourcing should be gone
        self.assertNotIn(b"Data Sourcing", response.data)

    def test_user_access_control(self):
        # Login as User
        self.client.post('/login', data={
            'username': 'AristotleLogic',
            'password': USERS['AristotleLogic']['password']
        })

        # Try accessing Strategies
        response = self.client.get('/strategies', follow_redirects=True)
        # Should be redirected to Dashboard and show flash message
        self.assertIn(b"You are not authorized", response.data)

        # Try accessing Guided Learning
        response = self.client.get('/guided_learning', follow_redirects=True)
        self.assertIn(b"You are not authorized", response.data)

    def test_settings_page_user(self):
        # Login as User
        self.client.post('/login', data={
            'username': 'AristotleLogic',
            'password': USERS['AristotleLogic']['password']
        })

        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Connect Your Amazon Account", response.data)
        self.assertNotIn(b"manual_sp_api_token", response.data)
        self.assertIn(b"Amazon SP-API Integration is not connected.", response.data)

    def test_settings_page_admin(self):
        # Login as Admin
        self.client.post('/login', data={
            'username': 'tester',
            'password': USERS['tester']['password']
        })

        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Connect Your Amazon Account", response.data)

if __name__ == '__main__':
    unittest.main()
