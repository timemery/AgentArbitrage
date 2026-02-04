import sys
import os
import json
from flask import session

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wsgi_handler import app

def test_chat_api():
    with app.test_client() as client:
        # Simulate Login
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'tester'
            sess['role'] = 'admin'

        print("Testing /api/mentor-chat with mentor='errol'...")
        payload = {
            'message': 'What should I look for in a book deal?',
            'mentor': 'errol'
        }

        response = client.post('/api/mentor-chat',
                             data=json.dumps(payload),
                             content_type='application/json')

        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.get_json()
            if 'reply' in data:
                print("Success! Reply received:")
                print(data['reply'])
            elif 'error' in data:
                print(f"API Error: {data['error']}")
            else:
                print("Unknown response format:", data)
        else:
            print("Failed.")
            print(response.data.decode('utf-8'))

if __name__ == "__main__":
    test_chat_api()
