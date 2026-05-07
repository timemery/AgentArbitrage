import os
import sys
import json
import requests
import time

def check_xai_connection():
    print("--- xAI API Connection Diagnostic ---")

    # Try to load from .env file if dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("[+] Loaded environment variables from .env file (if present).")
    except ImportError:
        print("[-] python-dotenv not installed, relying on existing environment variables.")

    xai_token = os.getenv("XAI_TOKEN")

    if not xai_token:
        print("\n[ERROR] XAI_TOKEN environment variable is not set!")
        print("Please ensure your .env file contains XAI_TOKEN=your_api_key_here")
        sys.exit(1)

    masked_key = f"{xai_token[:5]}...{xai_token[-5:]}" if len(xai_token) > 10 else "***"
    print(f"[+] Found XAI_TOKEN: {masked_key}")

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {xai_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful diagnostic assistant."},
            {"role": "user", "content": "Please reply with the word 'SUCCESS' and nothing else."}
        ],
        "model": "grok-4-fast-reasoning",
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 10
    }

    print(f"\n[+] Sending request to {url}...")
    print(f"[+] Using model: {payload['model']}")

    start_time = time.time()

    try:
        # We use a 30 second timeout to prevent indefinite hanging
        response = requests.post(url, headers=headers, json=payload, timeout=30.0)
        elapsed_time = time.time() - start_time

        print(f"\n[+] Request completed in {elapsed_time:.2f} seconds.")
        print(f"[+] HTTP Status Code: {response.status_code}")

        if response.status_code == 200:
            print("\n[SUCCESS] Successfully connected to xAI API!")
            response_data = response.json()
            message = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"[+] AI Response: {message.strip()}")
        else:
            print("\n[FAILED] API returned a non-200 status code.")
            print(f"[+] Response Body: {response.text}")

    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"\n[ERROR] Request timed out after {elapsed_time:.2f} seconds!")
        print("This usually indicates a network issue, firewall block, or the xAI API is completely unresponsive.")
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] A network error occurred: {e}")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    check_xai_connection()
