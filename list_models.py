import os
import httpx
import json

XAI_TOKEN = os.getenv("XAI_TOKEN")
headers = {
    "Authorization": f"Bearer {XAI_TOKEN}",
    "Content-Type": "application/json"
}

with httpx.Client() as client:
    response = client.get("https://api.x.ai/v1/models", headers=headers)
    print(json.dumps(response.json(), indent=2))
