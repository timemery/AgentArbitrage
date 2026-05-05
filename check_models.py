import json
import logging
from keepa_deals.ava_advisor import query_xai_api

logging.basicConfig(level=logging.INFO)

payload = {
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "model": "grok-2",
    "stream": False,
    "temperature": 0.5
}

response = query_xai_api(payload)
print(json.dumps(response, indent=2))
