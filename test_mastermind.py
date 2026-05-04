import keepa_deals.ava_advisor as advisor
import json

payload = {
    "messages": [
        {"role": "system", "content": "You are a test bot."},
        {"role": "user", "content": 'Return a JSON array with one element "test". Only return JSON, no markdown.'}
    ],
    "model": "grok-4-fast-reasoning",
    "stream": False,
    "temperature": 0.2
}

try:
    response = advisor.query_xai_api(payload)
    print("Response successful.")
except Exception as e:
    print(e)
