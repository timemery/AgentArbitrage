import requests
import json
import os

XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_TOKEN = os.getenv("XAI_TOKEN")

payload = {
    "messages": [
        {"role": "system", "content": "You are a precise JSON-only output bot."},
        {"role": "user", "content": 'Please reply with ["TEST"]'}
    ],
    "model": "grok-beta",
    "stream": False,
    "temperature": 0.2
}

headers = {
    "Authorization": f"Bearer {XAI_TOKEN}",
    "Content-Type": "application/json"
}

try:
    print("Sending request to xAI...")
    response = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
