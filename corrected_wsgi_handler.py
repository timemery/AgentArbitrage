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
            "messages": [{"role": "system", "content": "You are an expert in online book arbitrage. Your task is to extract key strategies and parameters from the provided text and present them as a list of clear, actionable rules."}, {"role": "user", "content": prompt}],
            "model": "grok-4-latest", "stream": False, "temperature": 0.2
        }
        primary_data = query_xai_api(xai_payload)
        if primary_data and 'choices' in primary_data and primary_data['choices']:
            content = primary_data['choices'][0].get('message', {}).get('content')
            if content:
                flash("Successfully extracted strategies.", "success")
                app.logger.info("Successfully extracted strategies using xAI API.")
                return content
        app.logger.warning(f"Primary strategy extraction with xAI failed: {primary_data}. Falling back to summary model.")
        flash(f"xAI API failed ({primary_data.get('error', 'Unknown Error')}). Falling back to a secondary model.", "warning")
        fallback_payload = {"inputs": prompt, "parameters": {"min_length": 20, "max_length": 100}}
        fallback_data = query_huggingface_api(fallback_payload, SUMMARY_API_URL)
        if isinstance(fallback_data, list) and fallback_data:
            if 'summary_text' in fallback_data[0]:
                flash("Fallback model succeeded.", "success")
                app.logger.info(f"Successfully generated fallback strategies using {SUMMARY_API_URL}.")
                return f"FALLBACK: The primary strategy model is currently unavailable. The following is a response from the backup model:\n\n{fallback_data[0]['summary_text']}"
            elif 'generated_text' in fallback_data[0]:
                flash("Fallback model succeeded.", "success")
                app.logger.info(f"Successfully generated fallback strategies using {SUMMARY_API_URL} (generated_text).")
                return f"FALLBACK: The primary strategy model is currently unavailable. The following is a response from the backup model:\n\n{fallback_data[0]['generated_text']}"
        error_message = f"Primary model (xAI) failed ({primary_data.get('error', 'Unknown Error')}). Fallback model also failed or returned invalid data: {fallback_data}"
        app.logger.error(error_message)
        flash("Error: Both the primary and fallback models failed to extract strategies.", "error")
        return "Could not extract strategies. Both primary and fallback models failed. Please check the logs."

    def chunk_text(text, chunk_size=512):
        words = text.split()
        chunks = []
        current_chunk = ""
        for word in words:
            if len(current_chunk) + len(word) + 1 < chunk_size:
                current_chunk += word + " "
            else:
                chunks.append(current_chunk)
                current_chunk = word + " "
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def get_youtube_transcript_with_selenium(url: str) -> str:
        app.logger.info(f"Attempting to fetch transcript for {url} using Selenium.")

        # Use a managed temporary directory for the user profile.
        # This directory and its contents will be automatically removed when the 'with' block is exited.
        with tempfile.TemporaryDirectory() as user_data_dir:
            app.logger.info(f"Using managed temporary user-data-dir: {user_data_dir}")

            os.environ["WDM_LOCAL"] = "1"
            os.environ["WDM_DIR"] = "/tmp/wdm"
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument(f'--user-data-dir={user_data_dir}')
            options.binary_location = "/usr/bin/google-chrome"

            driver = None
            service = None
            try:
                driver_path = ChromeDriverManager().install()
                service = ChromeService(driver_path)
                driver = webdriver.Chrome(service=service, options=options)

                driver.get(url)

                more_actions_button_xpath = "//button[@aria-label='More actions']"
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, more_actions_button_xpath))
                ).click()

                show_transcript_button_xpath = "//yt-formatted-string[text()='Show transcript']"
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, show_transcript_button_xpath))
                ).click()

                transcript_segment_xpath = "//yt-formatted-string[contains(@class, 'segment-text')]"
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, transcript_segment_xpath))
                )

                transcript_elements = driver.find_elements(By.XPATH, transcript_segment_xpath)
                transcript_text = " ".join([elem.text for elem in transcript_elements])

                app.logger.info("Successfully fetched transcript with Selenium.")
                return transcript_text

            except Exception as e:
                app.logger.error(f"Selenium error: {e}", exc_info=True)
                return f"Error: Failed to fetch transcript with Selenium: {e}"
            finally:
                # The browser process MUST be terminated before the temporary directory can be cleaned up.
                if driver:
                    driver.quit()
                if service:
                    service.stop()

    # --- Flask Routes ---

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login', methods=['POST'])
    def login():
        username = request.form.get('username')
        password = request.form.get('password')
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session.clear()
            session['logged_in'] = True
            return redirect(url_for('guided_learning'))
        else:
            return 'Invalid credentials', 401

    @app.route('/guided_learning')
    def guided_learning():
        if session.get('logged_in'):
            return render_template('guided_learning.html')
        else:
            return redirect(url_for('index'))

    @app.route('/learn', methods=['POST'])
    def learn():
        if not session.get('logged_in'):
            return redirect(url_for('index'))

        session.pop('original_input', None)
        learning_text = request.form.get('learning_text', '')
        session['original_input'] = learning_text[:5000]

        scraped_text = ""
        youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(?:embed\/)?(?:v\/)?(?:shorts\/)?([\w-]{11})(?:\S+)?'
        if re.match(youtube_regex, learning_text):
            scraped_text = get_youtube_transcript_with_selenium(learning_text)
        elif re.match(r'http[s]?://', learning_text):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                with httpx.Client(headers=headers, follow_redirects=True) as client:
                    response = client.get(learning_text)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for element in soup(["script", "style", "nav", "footer", "header"]):
                        element.extract()
                    scraped_text = soup.get_text(separator='\n', strip=True)
            except httpx.RequestError as e:
                scraped_text = f"Error scraping URL: {e}"
                app.logger.error(scraped_text)
        else:
            scraped_text = learning_text

        scraped_text = scraped_text[:50000]

        summary_text = ""
        try:
            if len(scraped_text) > 1024:
                text_chunks = chunk_text(scraped_text)
                summaries = []
                for i, chunk in enumerate(text_chunks):
                    summary_payload = {"inputs": chunk, "parameters": {"min_length": 30, "max_length": 150}}
                    summary_data = query_huggingface_api(summary_payload, SUMMARY_API_URL)
                    if isinstance(summary_data, list) and summary_data and 'summary_text' in summary_data[0]:
                        summaries.append(summary_data[0]['summary_text'])
                    else:
                        app.logger.error(f"Could not summarize chunk {i+1}. API response: {summary_data}")
                # Fixed bug: was using "\\n" which is a literal backslash-n, not a newline.
                summary_text = "\n".join(summaries) if summaries else "Could not generate a summary."
            else:
                summary_payload = {"inputs": scraped_text, "parameters": {"min_length": 30, "max_length": 150}}
                summary_data = query_huggingface_api(summary_payload, SUMMARY_API_URL)
                if isinstance(summary_data, list) and summary_data and 'summary_text' in summary_data[0]:
                    summary_text = summary_data[0]['summary_text']
                else:
                    summary_text = f"Could not summarize the text. API Response: {summary_data}"
        except Exception as e:
            app.logger.error(f"An error occurred during summarization: {e}", exc_info=True)
            summary_text = "An error occurred during summarization."

        extracted_strategies = extract_strategies(summary_text)

        # Store results in session to pass to the results page
        session['results_data'] = {
            'original_input': learning_text[:5000],
            'scraped_text': scraped_text,
            'summary': summary_text,
            'extracted_strategies': extracted_strategies
        }
        return redirect(url_for('results'))

    @app.route('/results')
    def results():
        if not session.get('logged_in'):
            return redirect(url_for('index'))
        results_data = session.get('results_data', {})
        return render_template('results.html', **results_data)

    @app.route('/clear_session')
    def clear_session():
        session.clear()
        flash('Session cleared!', 'success')
        return redirect(url_for('guided_learning'))

    # --- WSGI Application Entry Point ---
    application = app

except Exception as e:
    # Fallback error logging if the main app fails to initialize
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        error_file = os.path.join(script_dir, 'startup_error.txt')
        with open(error_file, "w") as f:
            f.write("A fatal error occurred on startup:\n")
            f.write(traceback.format_exc())
    except Exception:
        # If writing to the app directory fails, write to /tmp
        with open("/tmp/startup_error.txt", "w") as f:
            f.write("A fatal error occurred on startup (and writing to app dir failed):\n")
            f.write(traceback.format_exc())
