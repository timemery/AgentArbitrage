from flask import Flask, render_template, request, redirect, url_for, session, flash
import httpx
from bs4 import BeautifulSoup
import re
import json
from dotenv import load_dotenv
import os
import logging
import tempfile
import time
load_dotenv('/var/www/agentarbitrage/.env')

app = Flask(__name__)

# Configure logging
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
app.secret_key = 'supersecretkey'  # It's important to set a secret key for sessions

# --- Hugging Face API Configuration ---
HUGGING_FACE_API_KEY = os.getenv("HF_TOKEN")
SUMMARY_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
STRATEGY_API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"

app.logger.info(f"Loaded HF_TOKEN: {HUGGING_FACE_API_KEY}")

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

def extract_strategies(summary_text):
    prompt = f"""
    From the following text, extract the key strategies and parameters for online book arbitrage.
    Present them as a list of rules. For example: "Sales rank between 100,000 and 500,000".

    Text:
    {summary_text}
    """
    # Attempt 1: Primary Model (flan-t5-large)
    primary_payload = {"inputs": prompt, "parameters": {"max_new_tokens": 512, "temperature": 0.7, "do_sample": True}}
    primary_data = query_huggingface_api(primary_payload, STRATEGY_API_URL)

    if isinstance(primary_data, list) and primary_data and 'generated_text' in primary_data[0]:
        flash("Successfully extracted strategies using the primary model (google/flan-t5-large).", "success")
        app.logger.info(f"Successfully extracted strategies using {STRATEGY_API_URL}.")
        return primary_data[0]['generated_text']

    # Attempt 2: Fallback Model (bart-large-cnn)
    app.logger.warning(f"Primary strategy extraction failed: {primary_data}. Falling back to summary model.")
    flash(f"Primary model failed ({primary_data.get('error', 'Unknown Error')}). Falling back to a secondary model.", "warning")

    fallback_payload = {"inputs": prompt, "parameters": {"min_length": 20, "max_length": 100}}
    fallback_data = query_huggingface_api(fallback_payload, SUMMARY_API_URL)

    if isinstance(fallback_data, list) and fallback_data:
        if 'summary_text' in fallback_data[0]:
            flash("Fallback model succeeded.", "success")
            app.logger.info(f"Successfully generated fallback strategies using {SUMMARY_API_URL}.")
            return f"FALLBACK: The primary strategy model is currently unavailable. The following is a response from the backup model:\n\n{fallback_data[0]['summary_text']}"
        elif 'generated_text' in fallback_data[0]: # Some models might return this key instead
            flash("Fallback model succeeded.", "success")
            app.logger.info(f"Successfully generated fallback strategies using {SUMMARY_API_URL} (generated_text).")
            return f"FALLBACK: The primary strategy model is currently unavailable. The following is a response from the backup model:\n\n{fallback_data[0]['generated_text']}"

    # Final Failure
    error_message = f"Primary model failed ({primary_data.get('error', 'Unknown Error')}). Fallback model also failed or returned invalid data: {fallback_data}"
    app.logger.error(error_message)
    flash("Error: Both the primary and fallback models failed to extract strategies.", "error")
    return "Could not extract strategies. Both primary and fallback models failed. Please check the logs."


def chunk_text(text, chunk_size=512): # Smaller chunks - changed from 1024 to 512
    """Splits the text into chunks of a specified size."""
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

# Credentials from README.md
VALID_USERNAME = 'tester'
VALID_PASSWORD = 'OnceUponaBurgerTree-12monkeys'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == VALID_USERNAME and password == VALID_PASSWORD:
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
    
    # Clean up old temp files
    for key in ['scraped_text_file', 'summary_file']:
        if key in session:
            try:
                os.remove(session[key])
            except OSError:
                pass
            session.pop(key, None)

    session.pop('original_input', None)
    
    app.logger.info("Inside learn route")
    app.logger.info(f"Request form: {request.form}")
    if 'learning_text' in request.form:
        learning_text = request.form['learning_text']
        app.logger.info(f"Received learning text: {learning_text}")
        session['original_input'] = learning_text[:5000]  # Reduce to 5,000 chars   
    else:
        app.logger.warning("learning_text not in request.form")
        learning_text = ""
        session['original_input'] = ""
    
    scraped_text = ""
    if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', learning_text):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
            }
            with httpx.Client(headers=headers, follow_redirects=True) as client:
                response = client.get(learning_text)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                for script in soup(["script", "style"]):
                    script.extract()
                scraped_text = soup.get_text()
                lines = (line.strip() for line in scraped_text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                scraped_text = '\n'.join(chunk for chunk in chunks if chunk)
        except httpx.HTTPStatusError as e:
            scraped_text = f"Error scraping URL: {e.response.status_code} {e.response.reason_phrase} for url: {e.request.url}"
        except httpx.RequestError as e:
            scraped_text = f"Error scraping URL: {e}"
    else:
        scraped_text = learning_text

        scraped_text = scraped_text[:50000]  # Limit to 50,000 characters for summarization

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as f:
        f.write(scraped_text)
        session['scraped_text_file'] = f.name

    summary_text = ""
    app.logger.info("Starting summarization...")
    try:
        app.logger.info(f"Text to summarize (first 100 chars): {scraped_text[:100]}")
        if len(scraped_text) > 1024:
            app.logger.info("Text is long, chunking...")
            text_chunks = chunk_text(scraped_text)
            summaries = []
            for i, chunk in enumerate(text_chunks):
                app.logger.info(f"Summarizing chunk {i+1}/{len(text_chunks)}")
                summary_payload = {"inputs": chunk, "parameters": {"min_length": 30, "max_length": 150}}
                summary_data = query_huggingface_api(summary_payload, SUMMARY_API_URL)
                if isinstance(summary_data, list) and summary_data and 'summary_text' in summary_data[0]:
                    summaries.append(summary_data[0]['summary_text'])
                else:
                    app.logger.error(f"Could not summarize chunk {i+1}. API response: {summary_data}")
            summary_text = "\n".join(summaries) if summaries else "Could not generate a summary."
        else:
            app.logger.info("Text is short, summarizing directly...")
            summary_payload = {"inputs": scraped_text, "parameters": {"min_length": 30, "max_length": 150}}
            summary_data = query_huggingface_api(summary_payload, SUMMARY_API_URL)
            if isinstance(summary_data, list) and summary_data and 'summary_text' in summary_data[0]:
                summary_text = summary_data[0]['summary_text']
            else:
                app.logger.error(f"Could not summarize text. API response: {summary_data}")
                summary_text = f"Could not summarize the text. API Response: {summary_data}"
    except Exception as e:
        app.logger.error(f"An error occurred during summarization: {e}", exc_info=True)
        summary_text = "An error occurred during summarization."
    app.logger.info("Summarization finished.")

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as f:
        f.write(summary_text)
        session['summary_file'] = f.name

    extracted_strategies = extract_strategies(summary_text)
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as f:
        f.write(extracted_strategies)
        session['extracted_strategies_file'] = f.name

    return redirect(url_for('results'))

@app.route('/results')
def results():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    original_input = session.get('original_input', '')
    
    scraped_text = ""
    if 'scraped_text_file' in session:
        try:
            with open(session['scraped_text_file'], 'r', encoding='utf-8') as f:
                scraped_text = f.read()
        except FileNotFoundError:
            scraped_text = "Could not find scraped text."

    summary = ""
    if 'summary_file' in session:
        try:
            with open(session['summary_file'], 'r', encoding='utf-8') as f:
                summary = f.read()
        except FileNotFoundError:
            summary = "Could not find summary."

    extracted_strategies = ""
    if 'extracted_strategies_file' in session:
        try:
            with open(session['extracted_strategies_file'], 'r', encoding='utf-8') as f:
                extracted_strategies = f.read()
        except FileNotFoundError:
            extracted_strategies = "Could not find extracted strategies."

    return render_template('results.html', original_input=original_input, scraped_text=scraped_text, summary=summary, extracted_strategies=extracted_strategies)

@app.route('/approve', methods=['POST'])
def approve():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    approved_summary = request.form.get('approved_summary')
    approved_strategies = request.form.get('approved_strategies')
    
    app.logger.info("Approved Summary:")
    app.logger.info(approved_summary)
    
    app.logger.info("Approved Strategies:")
    app.logger.info(approved_strategies)
    
    # For now, just redirect back to the main app page
    return redirect(url_for('guided_learning'))

@app.route('/clear_session')
def clear_session():
    # Clean up old temp files
    for key in ['scraped_text_file', 'summary_file', 'extracted_strategies_file']:
        if key in session:
            try:
                os.remove(session[key])
            except OSError:
                pass
            session.pop(key, None)
    
    # Also remove original_input from session, but keep 'logged_in'
    session.pop('original_input', None)

    flash('Session cleared!', 'success')
    return redirect(url_for('guided_learning'))

@app.route('/test_route', methods=['POST'])
def test_route():
    app.logger.info("Test route called!")
    return "Test route called!"

if __name__ == '__main__':
    app.run(debug=True)