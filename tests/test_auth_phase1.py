import pytest
from wsgi_handler import app, USERS

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    with app.test_client() as client:
        yield client

def test_login_admin(client):
    response = client.post('/login', data={
        'username': 'tester',
        'password': USERS['tester']['password']
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to Guided Learning (checked by content)
    # Note: Guided Learning template might not say "Guided Learning" in body if empty, but header has it.
    # The title block says "Agent Arbitrage", main-nav has "Guided Learning".
    # Let's check for "Intelligence" link presence which implies Admin nav.
    assert b'href="/intelligence"' in response.data
    # Data Sourcing should be gone
    assert b"Data Sourcing" not in response.data

def test_login_user(client):
    response = client.post('/login', data={
        'username': 'AristotleLogic',
        'password': USERS['AristotleLogic']['password']
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to Dashboard
    # Dashboard page has "Dashboard" in title or nav.
    # Check that "Strategies" link is NOT present
    assert b'href="/strategies"' not in response.data
    # Data Sourcing should be gone
    assert b"Data Sourcing" not in response.data

def test_user_access_control(client):
    # Login as User
    client.post('/login', data={
        'username': 'AristotleLogic',
        'password': USERS['AristotleLogic']['password']
    })

    # Try accessing Strategies
    response = client.get('/strategies', follow_redirects=True)
    # Should be redirected to Dashboard and show flash message
    assert b"You are not authorized" in response.data

    # Try accessing Guided Learning
    response = client.get('/guided_learning', follow_redirects=True)
    assert b"You are not authorized" in response.data

def test_settings_page_user(client):
    # Login as User
    client.post('/login', data={
        'username': 'AristotleLogic',
        'password': USERS['AristotleLogic']['password']
    })

    response = client.get('/settings')
    assert response.status_code == 200
    # Should not see "Connect Your Amazon Account" button link if not connected
    # In test environment, sp_api_connected is False by default.
    assert b"Connect Your Amazon Account" not in response.data
    # Should not see Manual Connection form
    assert b"manual_sp_api_token" not in response.data
    # Should see "Amazon SP-API Integration is not connected."
    assert b"Amazon SP-API Integration is not connected." in response.data

def test_settings_page_admin(client):
    # Login as Admin
    client.post('/login', data={
        'username': 'tester',
        'password': USERS['tester']['password']
    })

    response = client.get('/settings')
    assert response.status_code == 200
    # Should see Connect button or form (since not connected in test)
    assert b"Connect Your Amazon Account" in response.data
