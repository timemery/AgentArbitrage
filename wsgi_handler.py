import os
import sys
import traceback
import logging
import threading

try:
    # This combines the logic from app-beforeeverythinggotscrewedup.py with WSGI requirements.
    from flask import Flask, render_template, request, redirect, url_for, session, flash
    import httpx
    from bs4 import BeautifulSoup
    import re
    import json
    from dotenv import load_dotenv
    import tempfile
    import time
    import requests
    import shutil
    import psutil
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    # Explicitly load .env from the correct path for the WSGI environment
    load_dotenv('/var/www/agentarbitrage/.env')

    # --- Flask App Initialization ---
    app = Flask(__name__)
    app.secret_key = 'supersecretkey'

    # --- Logging Configuration ---
    # Ensure logs are written to a file in the application directory
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
    
    app.logger.info(f"--- WSGI application starting up in process {os.getpid()} ---")

    # --- API and Credentials Configuration ---
    HUGGING_FACE_API_KEY = os.getenv("HF_TOKEN")
    SUMMARY_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
    XAI_API_KEY = os.getenv("XAI_TOKEN")
    XAI_API_URL = "https://api.x.ai/v1/chat/completions"
    VALID_USERNAME = 'tester'
    VALID_PASSWORD = 'OnceUponaBurgerTree-12monkeys'

    app.logger.info(f"Loaded HF_TOKEN: {'Exists' if HUGGING_FACE_API_KEY else 'Not found'}")
    app.logger.info(f"Loaded XAI_TOKEN: {'Exists' if XAI_API_KEY else 'Not found'}")

    # --- Helper Functions ---

    def query_huggingface_api(payload, api_url):
        headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}
        for i in range(3): # Retry up to 3 times
            with httpx.Client(timeout=None) as client:
                response = client.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    app.logger.error(f"Failed to decode JSON from Hugging Face API. Response status: {response.status_code}, content: {response.text}")
                    return {"error": "Invalid response from API"}
            elif response.status_code == 503:
                app.logger.warning(f"API request failed with status 503 (model loading?). Retrying in 5 seconds... (Attempt {i+1}/3)")
                time.sleep(5)
                continue
            else:
                break # Don't retry for other errors
        app.logger.error(f"API request failed after retries. Status: {response.status_code}, Response: {response.text}")
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"error": f"API request failed with status {response.status_code}", "content": response.text}

    def query_xai_api(payload):
        if not XAI_API_KEY:
            app.logger.error("XAI_TOKEN is not set.")
            return {"error": "XAI_TOKEN is not configured."}
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }
        with httpx.Client(timeout=30.0) as client:
            try:
                response = client.post(XAI_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                app.logger.error(f"xAI API request failed with status {e.response.status_code}: {e.response.text}")
                return {"error": f"API request failed with status {e.response.status_code}", "content": e.response.text}
            except (httpx.RequestError, json.JSONDecodeError) as e:
                app.logger.error(f"xAI API request failed: {e}")
                return {"error": str(e)}

    def extract_strategies(summary_text):
        # Using a triple-quoted f-string for better readability and to avoid escaping quotes.
        prompt = f'''From the following text, extract the key strategies and parameters for online book arbitrage.
Present them as a list of rules. For example: "Sales rank between 100,000 and 500,000".

Text:
{summary_text}'''
        xai_payload = {
            "messages": [{"role": "system", "content": "You are an expert in online book arbitrage. Y