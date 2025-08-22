import sys
import logging
import os
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, flash
import httpx
from bs4 import BeautifulSoup
import re
import json
from dotenv import load_dotenv
import tempfile
import time
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
logging.getLogger('app').info(f"Starting wsgi_handler.py from /var/www/agentarbitrage/wsgi_handler.py")
logging.getLogger('app').info(f"Python version: {sys.version}")
logging.getLogger('app').info(f"Python path: {sys.path}")

load_dotenv('/var/www/agentarbitrage/.env')
logging.getLogger('app').info(f"Loaded wsgi_handler.py from /var/www/agentarbitrage/wsgi_handler.py at {os.getpid()}")

app = Flask(__name__)
app.secret_key = 'supersecretkey'

STRATEGIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategies.json')

# --- Hugging Face API Configuration ---
HUGGING_FACE_API_KEY = os.getenv("HF_TOKEN")
SUMMARY_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

# --- xAI API Configuration ---
XAI_API_KEY = os.getenv("XAI_TOKEN")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

app.logger.info(f"Loaded HF_TOKEN: {HUGGING_FACE_API_KEY}")
app.logger.info(f"Loaded XAI_TOKEN: {'*' * len(XAI_API_KEY) if XAI_API_KEY else 'Not found'}")

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
    with httpx.Client(timeout=90.0) as client:
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
    prompt = f"""
    From the following text, extract the key strategies and parameters for online book arbitrage.
    Present them as a list of rules. For example: "Sales rank between 100,000 and 500,000".

    Only use the information from the text provided. Do not add any external knowledge.
    If the text is not about online book arbitrage or contains no actionable strategies, respond with the single phrase: "No actionable strategies found in the provided text."

    Text:
    {summary_text}
    """

    # Attempt 1: Primary Model (xAI)
    xai_payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in online book arbitrage. Your task is to extract key strategies and parameters from the provided text and present them as a list of clear, actionable rules."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "model": "grok-4-latest",
        "stream": False,
        "temperature": 0.2
    }
    
    primary_data = query_xai_api(xai_payload)

    if primary_data and 'choices' in primary_data and primary_data['choices']:
        content = primary_data['choices'][0].get('message', {}).get('content')
        if content:
            flash("Successfully extracted strategies.", "success")
            app.logger.info("Successfully extracted strategies using xAI API.")
            return content
    
    # If xAI API fails, report the error directly.
    error_message = f"Strategy extraction failed. The primary model (xAI) returned an error: {primary_data.get('error', 'Unknown Error')}"
    app.logger.error(error_message)
    flash("Error: Could not extract strategies. The primary model failed.", "error")
    return "Could not extract strategies. Please check the logs for details."


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
        session.clear()  # Clear all session data
        session['logged_in'] = True
        return redirect(url_for('guided_learning'))
    else:
        return 'Invalid credentials', 401

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/guided_learning')
def guided_learning():
    if session.get('logged_in'):
        return render_template('guided_learning.html')
    else:
        return redirect(url_for('index'))

@app.route('/strategies')
def strategies():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    strategies_list = []
    app.logger.info(f"Attempting to read strategies from: {STRATEGIES_FILE}")
    if os.path.exists(STRATEGIES_FILE):
        app.logger.info(f"Strategies file found.")
        try:
            with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
                strategies_list = json.load(f)
            app.logger.info(f"Successfully loaded {len(strategies_list)} strategies.")
        except (IOError, json.JSONDecodeError) as e:
            app.logger.error(f"Error reading strategies file: {e}", exc_info=True)
            flash("Error reading the strategies file.", "error")
    else:
        app.logger.warning(f"Strategies file not found at: {STRATEGIES_FILE}")

    return render_template('strategies.html', strategies=strategies_list)

@app.route('/learn', methods=['POST'])
def learn():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    # Clean up old temp files
    for key in ['scraped_text_file', 'summary_file', 'extracted_strategies_file']:
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
        session['original_input'] = learning_text[:5000]
    else:
        app.logger.warning("learning_text not in request.form")
        learning_text = ""
        session['original_input'] = ""
    
    scraped_text = ""
    # Regex to find YouTube video ID from various URL formats
    youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(?:embed\/)?(?:v\/)?(?:shorts\/)?([\w-]{11})(?:\S+)?'
    youtube_match = re.match(youtube_regex, learning_text)

    if youtube_match:
        scraped_text = get_youtube_transcript(learning_text)
    elif re.match(r'http[s]?://', learning_text):
        app.logger.info("Non-YouTube URL detected. Scraping page.")
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
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.extract()
                scraped_text = soup.get_text(separator='\n', strip=True)
        except httpx.HTTPStatusError as e:
            scraped_text = f"Error scraping URL: {e.response.status_code} {e.response.reason_phrase} for url: {e.request.url}"
            app.logger.error(scraped_text)
        except httpx.RequestError as e:
            scraped_text = f"Error scraping URL: {e}"
            app.logger.error(scraped_text)
    else:
        app.logger.info("Plain text input detected.")
        scraped_text = learning_text

    scraped_text = scraped_text[:50000]

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as f:
        f.write(scraped_text)
        session['scraped_text_file'] = f.name

    summary_text = ""
    app.logger.info("Starting summarization...")
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

    # Save the approved strategies to a file
    if approved_strategies:
        try:
            # Load existing strategies
            if os.path.exists(STRATEGIES_FILE):
                with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
                    strategies = json.load(f)
            else:
                strategies = []
            
            # Add new strategy (or strategies)
            # Assuming strategies are newline-separated
            new_strategies = [s.strip() for s in approved_strategies.strip().split('\n') if s.strip()]
            strategies.extend(new_strategies)
            
            # Remove duplicates and save
            unique_strategies = list(dict.fromkeys(strategies))
            with open(STRATEGIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(unique_strategies, f, indent=4)
            
            flash(f"{len(new_strategies)} new strategies have been approved and saved.", "success")
        except Exception as e:
            app.logger.error(f"Error saving strategies: {e}", exc_info=True)
            flash("An error occurred while saving the strategies.", "error")


    # Clean up the session to prevent cookie size issues
    for key in ['scraped_text_file', 'summary_file', 'extracted_strategies_file', 'original_input']:
        if key in session:
            try:
                if session[key] and os.path.exists(session[key]):
                    os.remove(session[key])
            except (OSError, TypeError):
                pass
            session.pop(key, None)
    
    flash('Strategies approved and session cleared.', 'success')
    return redirect(url_for('guided_learning'))

@app.route('/clear_session')
def clear_session():
    for key in ['scraped_text_file', 'summary_file', 'extracted_strategies_file', 'original_input']:
        if key in session:
            try:
                if session[key] and os.path.exists(session[key]):
                    os.remove(session[key])
            except (OSError, TypeError):
                pass
            session.pop(key, None)
    session.clear()
    flash('Session cleared!', 'success')
    return redirect(url_for('guided_learning'))

@app.route('/test_route', methods=['POST'])
def test_route():
    app.logger.info("Test route called!")
    return "Test route called!"

def get_youtube_transcript(url: str) -> str:
    """
    Fetches the transcript of a YouTube video using the youtube-transcript-api library.
    """
    app.logger.info(f"Attempting to fetch transcript for {url} using youtube-transcript-api.")
    
    # Regex to find YouTube video ID
    youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(?:embed\/)?(?:v\/)?(?:shorts\/)?([\w-]{11})(?:\S+)?'
    match = re.search(youtube_regex, url)
    if not match:
        app.logger.error(f"Could not extract YouTube video ID from URL: {url}")
        return "Error: Could not extract YouTube video ID from URL."

    video_id = match.group(1)
    
    try:
        # --- Bright Data Proxy Configuration ---
        bd_user = os.getenv("BRIGHTDATA_USERNAME")
        bd_pass = os.getenv("BRIGHTDATA_PASSWORD")
        bd_host = os.getenv("BRIGHTDATA_HOST")

        proxy_config = None
        if all([bd_user, bd_pass, bd_host]):
            proxy_url = f'http://{bd_user}:{bd_pass}@{bd_host}:9222'
            proxy_config = GenericProxyConfig(
                http_url=proxy_url,
                https_url=proxy_url,
            )
            app.logger.info(f"Using Bright Data proxy: {bd_host}")
        else:
            app.logger.warning("Bright Data credentials not fully configured. Proceeding without proxy.")

        # Create an instance of the API, passing the proxy config if it exists
        api = YouTubeTranscriptApi(proxy_config=proxy_config)
        
        # The method is .list(), not .list_transcripts()
        transcript_list_obj = api.list(video_id)

        # Find the English transcript
        transcript = transcript_list_obj.find_transcript(['en'])
        
        # Fetch the transcript data
        transcript_data = transcript.fetch()
        
        # Join the text segments
        transcript_text = " ".join([item['text'] for item in transcript_data])
        
        app.logger.info(f"Successfully fetched transcript for video ID: {video_id}")
        return transcript_text
    except Exception as e:
        app.logger.error(f"Could not fetch transcript for video ID {video_id}: {e}", exc_info=True)
        return f"Error: Could not retrieve transcript. The video may have transcripts disabled, or an API error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
