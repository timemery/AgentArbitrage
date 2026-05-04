import json
import logging
from keepa_deals.ava_advisor import query_xai_api

# Setup logging
logging.basicConfig(level=logging.INFO)

payload = {
    "messages": [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "Hello, this is a test."}
    ],
    "model": "grok-4-fast-reasoning",
    "stream": False,
    "temperature": 0.5
}

response = query_xai_api(payload)
print(json.dumps(response, indent=2))
