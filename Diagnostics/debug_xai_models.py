import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wsgi_handler import query_xai_api

models = ["grok-4-fast-reasoning", "grok-4-fast-non-reasoning", "grok-4.20-non-reasoning", "grok-beta", "grok-4-0709", "grok-3-mini", "grok-2", "grok-3"]

for model in models:
    payload = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": model,
        "stream": False
    }
    res = query_xai_api(payload)
    if "error" in res:
        print(f"{model}: ERROR: {res['error']}")
    else:
        print(f"{model}: SUCCESS")
