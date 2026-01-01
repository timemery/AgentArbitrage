import json
import os
import uuid
import httpx
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

XAI_API_KEY = os.getenv("XAI_TOKEN")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
STRATEGIES_FILE = 'strategies.json'
OUTPUT_FILE = 'strategies_structured.json'

def query_xai_api(prompt):
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a data structuring assistant. Your task is to convert unstructured strategy text into a structured JSON format."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "model": "grok-4-fast-reasoning",
        "stream": False,
        "temperature": 0.2
    }

    try:
        response = httpx.post(XAI_API_URL, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error querying xAI: {e}")
        return None

def process_batch(batch):
    batch_text = json.dumps(batch, indent=2)
    prompt = f"""
    Convert the following list of strategy strings into a structured JSON array.

    Each item in the output array must follow this schema:
    {{
      "id": "generate a unique string ID here",
      "category": "One of: Buying, Pricing, Risk, Seasonality, General, Tools, Prepping",
      "trigger": "A short, logical condition description (e.g., 'Sales Rank > 1,000,000', 'Price Drop > 50%')",
      "advice": "The actionable advice or rule",
      "confidence": "High",
      "source": "The original text string provided"
    }}

    Return ONLY the JSON array. Do not include markdown formatting (like ```json).

    Input List:
    {batch_text}
    """

    result = query_xai_api(prompt)
    if result and 'choices' in result:
        content = result['choices'][0]['message']['content']
        # Clean up potential markdown code blocks
        content = content.replace('```json', '').replace('```', '').strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print("Failed to decode JSON response.")
            print(content)
            return []
    return []

def main():
    if not os.path.exists(STRATEGIES_FILE):
        print(f"File {STRATEGIES_FILE} not found.")
        return

    with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
        raw_strategies = json.load(f)

    print(f"Loaded {len(raw_strategies)} strategies.")

    structured_strategies = []
    batch_size = 20 # Smaller batch to ensure output JSON fits in response

    for i in range(0, len(raw_strategies), batch_size):
        batch = raw_strategies[i:i+batch_size]
        print(f"Processing batch {i // batch_size + 1} ({len(batch)} items)...")

        processed = process_batch(batch)
        if processed:
            # Ensure IDs are unique if the LLM reused them (unlikely but possible)
            for item in processed:
                item['id'] = str(uuid.uuid4())
            structured_strategies.extend(processed)

        # Rate limit friendly pause
        time.sleep(2)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(structured_strategies, f, indent=4)

    print(f"Migration complete. Saved {len(structured_strategies)} structured strategies to {OUTPUT_FILE}.")

if __name__ == "__main__":
    if not XAI_API_KEY:
        print("Error: XAI_TOKEN not found in environment. Please set it in .env or environment variables.")
    else:
        main()
