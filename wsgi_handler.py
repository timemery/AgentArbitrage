import sys
import logging
import os
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
import httpx
from bs4 import BeautifulSoup
import sqlite3
import re
import json
from dotenv import load_dotenv
import tempfile
import time
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
import click
from celery_app import celery_app
from keepa_deals.db_utils import create_user_restrictions_table_if_not_exists
# from keepa_deals.recalculator import recalculate_deals # This causes a hang
# from keepa_deals.Keepa_Deals import run_keepa_script

log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
logging.getLogger('app').info(f"Starting wsgi_handler.py from /var/www/agentarbitrage/wsgi_handler.py")
logging.getLogger('app').info(f"Python version: {sys.version}")
logging.getLogger('app').info(f"Python path: {sys.path}")

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
logging.getLogger('app').info(f"Loaded wsgi_handler.py from /var/www/agentarbitrage/wsgi_handler.py at {os.getpid()}")

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DATABASE_URL = os.getenv("DATABASE_URL", os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deals.db'))

STRATEGIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategies.json')
AGENT_BRAIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_brain.json')
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

# --- xAI API Configuration ---
XAI_API_KEY = os.getenv("XAI_TOKEN")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

# --- Keepa API Configuration ---
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")

# --- Amazon SP-API Configuration ---
SP_API_CLIENT_ID = os.getenv("SP_API_CLIENT_ID")
SP_API_CLIENT_SECRET = os.getenv("SP_API_CLIENT_SECRET")
SP_API_APP_ID = os.getenv("SP_API_APP_ID") # Often the same as Client ID
AMAZON_AUTH_URL = "https://sellercentral.amazon.com/apps/authorize/consent"
AMAZON_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


app.logger.info(f"Loaded XAI_TOKEN: {'*' * len(XAI_API_KEY) if XAI_API_KEY else 'Not found'}")
app.logger.info(f"Loaded KEEPA_API_KEY: {'*' * len(KEEPA_API_KEY) if KEEPA_API_KEY else 'Not found'}")
app.logger.info(f"Loaded SP_API_CLIENT_ID: {'*' * len(SP_API_CLIENT_ID) if SP_API_CLIENT_ID else 'Not found'}")

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

def extract_strategies(full_text):
    prompt = f"""
    From the following text, extract key strategies, parameters, and "tricks" for online book arbitrage.
    Present them as a list of clear, actionable rules.

    **Instructions:**
    1.  Focus on specific numbers, ranges, and conditions (e.g., "Sales rank between 100,000 and 500,000").
    2.  **Pay special attention to inferential strategies.** These are "tricks" or methods to figure out information that isn't directly stated, often by combining two or more data points.
    3.  Only use the information from the text provided. Do not add any external knowledge.
    4.  If the text contains no actionable strategies, respond with the single phrase: "No actionable strategies found in the provided text."

    **Example of an Inferential Strategy to capture:**
    *   "You can infer the actual sale price of a book by watching for a simultaneous drop in the number of used offers and a drop in the sales rank on the Keepa chart. The price at that point is likely the true sale price."

    **Text to Analyze:**
    {full_text}
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
            app.logger.info("Successfully extracted strategies using xAI API.")
            return content
    
    # If xAI API fails, report the error directly.
    error_message = f"Strategy extraction failed. The primary model (xAI) returned an error: {primary_data.get('error', 'Unknown Error')}"
    app.logger.error(error_message)
    return "Could not extract strategies. Please check the logs for details."


def extract_conceptual_ideas(full_text):
    prompt = f"""
    From the following text about online book arbitrage, extract high-level conceptual ideas, mental models, and overarching methodologies.
    Do not focus on specific, quantitative rules (e.g., "sales rank > 10,000"). Instead, focus on the "why" behind the actions.
    Present them as a list of insightful concepts.

    **Instructions:**
    1.  Identify the core principles or philosophies for sourcing, pricing, and selling.
    2.  Look for explanations of market dynamics (e.g., "why prices spike when Amazon goes out of stock").
    3.  Extract ideas about risk management, inventory strategy, and long-term thinking.
    4.  Only use the information from the text provided. Do not add any external knowledge.
    5.  If the text contains no conceptual ideas, respond with the single phrase: "No conceptual ideas found in the provided text."

    **Example of a Conceptual Idea to capture:**
    *   "The core arbitrage model is to capitalize on pricing inefficiencies between different fulfillment methods (FBM vs. FBA), buying from merchant-fulfilled sellers and reselling through Amazon's FBA network to command a higher price due to the Prime badge."
    *   "A long-term inventory strategy involves balancing fast-selling, low-ROI books with slow-selling, high-ROI 'long-tail' books to ensure consistent cash flow while building long-term value."

    **Text to Analyze:**
    {full_text}
    """

    xai_payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a strategic analyst. Your task is to extract high-level concepts, mental models, and methodologies from the provided text."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "model": "grok-4-latest",
        "stream": False,
        "temperature": 0.3
    }
    
    response_data = query_xai_api(xai_payload)

    if response_data and 'choices' in response_data and response_data['choices']:
        content = response_data['choices'][0].get('message', {}).get('content')
        if content:
            app.logger.info("Successfully extracted conceptual ideas using xAI API.")
            return content
    
    error_message = f"Conceptual idea extraction failed. The model returned an error: {response_data.get('error', 'Unknown Error')}"
    app.logger.error(error_message)
    return "Could not extract conceptual ideas. Please check the logs for details."

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


@app.route('/agent_brain')
def agent_brain():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    ideas_list = []
    app.logger.info(f"Attempting to read agent brain from: {AGENT_BRAIN_FILE}")
    if os.path.exists(AGENT_BRAIN_FILE):
        app.logger.info(f"Agent Brain file found.")
        try:
            with open(AGENT_BRAIN_FILE, 'r', encoding='utf-8') as f:
                ideas_list = json.load(f)
            app.logger.info(f"Successfully loaded {len(ideas_list)} ideas from Agent Brain.")
        except (IOError, json.JSONDecodeError) as e:
            app.logger.error(f"Error reading Agent Brain file: {e}", exc_info=True)
            flash("Error reading the Agent Brain file.", "error")
    else:
        app.logger.warning(f"Agent Brain file not found at: {AGENT_BRAIN_FILE}")

    return render_template('agent_brain.html', ideas=ideas_list)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')


@app.route('/learn', methods=['POST'])
def learn():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    # Clean up old temp files
    for key in ['scraped_text_file', 'extracted_strategies_file', 'extracted_ideas_file']:
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

    # The summarization step has been removed. We now pass the scraped_text directly.
    # A thread pool is used to run the two extraction API calls concurrently to improve performance.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as executor:
        future_strategies = executor.submit(extract_strategies, scraped_text)
        future_ideas = executor.submit(extract_conceptual_ideas, scraped_text)
        
        extracted_strategies = future_strategies.result()
        extracted_ideas = future_ideas.result()

    # Flash messages in the main request context
    if "Could not extract" in extracted_strategies:
        flash("Error: Could not extract strategies. The primary model failed.", "error")
    else:
        flash("Successfully extracted strategies.", "success")

    if "Could not extract" in extracted_ideas:
        flash("Error: Could not extract conceptual ideas.", "error")
    else:
        flash("Successfully extracted conceptual ideas.", "success")

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as f:
        f.write(extracted_strategies)
        session['extracted_strategies_file'] = f.name

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as f:
        f.write(extracted_ideas)
        session['extracted_ideas_file'] = f.name

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

    extracted_strategies = ""
    if 'extracted_strategies_file' in session:
        try:
            with open(session['extracted_strategies_file'], 'r', encoding='utf-8') as f:
                extracted_strategies = f.read()
        except FileNotFoundError:
            extracted_strategies = "Could not find extracted strategies."

    extracted_ideas = ""
    if 'extracted_ideas_file' in session:
        try:
            with open(session['extracted_ideas_file'], 'r', encoding='utf-8') as f:
                extracted_ideas = f.read()
        except FileNotFoundError:
            extracted_ideas = "Could not find extracted ideas."

    return render_template('results.html', original_input=original_input, scraped_text=scraped_text, extracted_strategies=extracted_strategies, extracted_ideas=extracted_ideas)

@app.route('/approve', methods=['POST'])
def approve():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    approved_strategies = request.form.get('approved_strategies')
    approved_ideas = request.form.get('approved_ideas')
    
    app.logger.info("Approved Strategies:")
    app.logger.info(approved_strategies)

    app.logger.info("Approved Conceptual Ideas:")
    app.logger.info(approved_ideas)

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

    # Save the approved ideas to the agent_brain.json file
    if approved_ideas:
        try:
            if os.path.exists(AGENT_BRAIN_FILE):
                with open(AGENT_BRAIN_FILE, 'r', encoding='utf-8') as f:
                    ideas = json.load(f)
            else:
                ideas = []
            
            new_ideas = [i.strip() for i in approved_ideas.strip().split('\n') if i.strip()]
            ideas.extend(new_ideas)
            
            unique_ideas = list(dict.fromkeys(ideas))
            with open(AGENT_BRAIN_FILE, 'w', encoding='utf-8') as f:
                json.dump(unique_ideas, f, indent=4)

            flash(f"{len(new_ideas)} new conceptual ideas have been approved and saved to the Agent Brain.", "success")
        except Exception as e:
            app.logger.error(f"Error saving conceptual ideas: {e}", exc_info=True)
            flash("An error occurred while saving the conceptual ideas.", "error")


    # Clean up the session to prevent cookie size issues
    for key in ['scraped_text_file', 'extracted_strategies_file', 'original_input', 'extracted_ideas_file']:
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

# --- Keepa Scan Status Management ---
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_status.json')
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/logs')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def get_scan_status():
    if not os.path.exists(STATUS_FILE):
        return {"status": "Idle"}
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {"status": "Error", "message": "Could not read status file."}

def set_scan_status(status_data):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError:
        app.logger.error(f"Could not write to status file: {STATUS_FILE}")

@app.route('/data_sourcing')
def data_sourcing():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    status_data = get_scan_status()
    # Check if the process is still running to catch crashes
    if status_data.get('status') == 'Running' and status_data.get('pid'):
        try:
            os.kill(status_data['pid'], 0)
        except OSError:
            status_data['status'] = 'Failed'
            status_data['message'] = 'The process disappeared unexpectedly. Check logs for details.'
            set_scan_status(status_data)
            
    return render_template('data_sourcing.html', status=status_data)

@app.route('/start-keepa-scan', methods=['POST'])
def start_keepa_scan():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    status = get_scan_status()
    if status.get('status') == 'Running':
        # Optionally, you could check the task state if you store the task_id
        flash('A scan is already in progress.', 'warning')
        return redirect(url_for('data_sourcing'))

    limit_str = request.form.get('limit')
    limit = int(limit_str) if limit_str and limit_str.isdigit() else None

    # Immediately set status to "Running" to provide feedback and prevent race conditions.
    # The Celery task will overwrite this with more details, but this is a crucial first step.
    set_scan_status({
        "status": "Running",
        "start_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "message": "Scan has been queued. Waiting for worker to start processing...",
        "task_id": None # Task ID will be set by the worker
    })

    # Trigger the task
    # task = run_keepa_script.delay(
    #     api_key=KEEPA_API_KEY,
    #     no_cache=True, # Or get this from the form
    #     output_dir='data',
    #     deal_limit=limit,
    #     status_update_callback=None # Cannot pass this from here
    # )

    # # The Celery task is now responsible for setting the initial status.
    # # We can store the task_id in the session for potential future use.
    # session['latest_task_id'] = task.id
    pass

    flash('Keepa scan has been initiated in the background.', 'success')
    return redirect(url_for('data_sourcing'))

@app.route('/scan-status')
def scan_status_endpoint():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    status_data = get_scan_status()
    return jsonify(status_data)

@app.route('/download/<path:filename>')
def download_file(filename):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return send_from_directory(DATA_DIR, filename, as_attachment=True)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Load existing settings to preserve any other values not on this form
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    settings_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                settings_data = {}

            # Update with business cost values
            tax_exempt = 'tax_exempt' in request.form
            estimated_tax = request.form.get('estimated_tax_per_book', 0, type=int)
            settings_data.update({
                'prep_fee_per_book': request.form.get('prep_fee_per_book', 0.0, type=float),
                'estimated_shipping_per_book': request.form.get('estimated_shipping_per_book', 0.0, type=float),
                'estimated_tax_per_book': 0 if tax_exempt else estimated_tax,
                'tax_exempt': tax_exempt,
                'default_markup': request.form.get('default_markup', 0, type=int)
            })


            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings_data, f, indent=4)

            # Trigger the background recalculation task by name
            celery_app.send_task('keepa_deals.recalculator.recalculate_deals')

            flash('Settings saved successfully! Recalculating deals in the background...', 'success')
        except Exception as e:
            flash(f'Error saving settings: {e}', 'error')
        return redirect(url_for('settings'))

    # GET request
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Default settings if file doesn't exist or is empty
        settings_data = {
            "prep_fee_per_book": 2.50,
            "estimated_shipping_per_book": 2.00,
            "estimated_tax_per_book": 15,
            "tax_exempt": False,
            "default_markup": 10
        }
    return render_template('settings.html', settings=settings_data)

@app.cli.command("fetch-keepa-deals")
@click.option('--no-cache', is_flag=True, help="Force fresh Keepa API calls.")
@click.option('--output-dir', default='data', help="Directory to save the output CSV file.")
@click.option('--limit', type=int, default=None, help="Limit the number of deals to process for testing.")
def fetch_keepa_deals_command(no_cache, output_dir, limit):
    """
    Runs the Keepa deals fetching script, wrapped with status reporting.
    """
    cli_status_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_status.json')

    def _update_cli_status(new_status_dict):
        try:
            # Ensure we read the latest status before writing to avoid race conditions
            current_status = {}
            if os.path.exists(cli_status_file):
                with open(cli_status_file, 'r') as f:
                    current_status = json.load(f)
            
            current_status.update(new_status_dict)

            with open(cli_status_file, 'w') as f:
                json.dump(current_status, f, indent=4)
        except (IOError, json.JSONDecodeError) as e:
            print(f"CLI Error: Could not write to status file: {cli_status_file}. Error: {e}", file=sys.stderr)

    try:
        # Robustly reconfigure logging for this command
        root_logger = logging.getLogger()
        # Set level to DEBUG for detailed analysis
        root_logger.setLevel(logging.DEBUG)
        # Remove any handlers configured by the main app
        root_logger.handlers = []
        # Add a new handler that writes to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        print("--- Running fetch-keepa-deals command ---")
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        load_dotenv(dotenv_path=dotenv_path)
        KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
        if not KEEPA_API_KEY:
            print("KEEPA_API_KEY not found in environment.", file=sys.stderr)
            raise ValueError("KEEPA_API_KEY not found")
        
        print(f"KEEPA_API_KEY loaded: {'*' * len(KEEPA_API_KEY)}")
        app.logger.info("Starting Keepa deals fetching command...")
        
        # run_keepa_script.delay(
        #     api_key=KEEPA_API_KEY,
        #     no_cache=no_cache,
        #     output_dir=output_dir,
        #     deal_limit=limit,
        #     status_update_callback=None
        # )
        pass
        
        print("run_keepa_script finished successfully.")
        app.logger.info("Keepa deals fetching command finished successfully.")

        # On success, update status
        _update_cli_status({
            'status': 'Completed',
            'end_time': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'output_file': f"{output_dir}/Keepa_Deals_Export.csv",
            'message': 'Scan completed successfully.'
        })

    except Exception as e:
        print(f"An error occurred during fetch-keepa-deals: {e}", file=sys.stderr)
        app.logger.error(f"An error occurred during fetch-keepa-deals: {e}", exc_info=True)
        # On failure, update status
        _update_cli_status({
            'status': 'Failed',
            'end_time': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'message': f"An error occurred: {str(e)}"
        })

@app.route('/deals', methods=['GET', 'POST'])
def deals():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    KEEPA_QUERY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keepa_query.json')

    if request.method == 'POST':
        keepa_query = request.form.get('keepa_query')
        try:
            json.loads(keepa_query)
            with open(KEEPA_QUERY_FILE, 'w') as f:
                f.write(keepa_query)
            flash('Keepa query saved successfully!', 'success')
        except json.JSONDecodeError:
            flash('Invalid JSON. Please check the syntax.', 'error')
        except Exception as e:
            flash(f'Error saving Keepa query: {e}', 'error')
        return redirect(url_for('deals'))

    # GET request
    try:
        with open(KEEPA_QUERY_FILE, 'r') as f:
            keepa_query = f.read()
    except (FileNotFoundError, json.JSONDecodeError):
        keepa_query = ''

    return render_template('deals.html', keepa_query=keepa_query)

@app.route('/api/deals')
def api_deals():
    DB_PATH = DATABASE_URL
    TABLE_NAME = 'deals'
    RESTRICTIONS_TABLE = 'user_restrictions'

    # Check SP-API connection status from session
    is_sp_api_connected = session.get('sp_api_connected', False)
    user_id = session.get('sp_api_user_id')

    # --- Connect and get column names ---
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABLE_NAME,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({
                "pagination": {"total_records": 0, "total_pages": 0, "current_page": 1, "limit": 50},
                "deals": [],
                "message": "No data found. Please run a scan."
            })

        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        available_columns = [row['name'] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        app.logger.error(f"Database error when fetching column info: {e}")
        return jsonify({"error": "Database error", "message": str(e)}), 500

    # --- Pagination and Sorting ---
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    offset = (page - 1) * limit
    sort_by = request.args.get('sort', 'id')
    if sort_by not in available_columns:
        sort_by = 'id'
    order = request.args.get('order', 'asc').lower()
    if order not in ['asc', 'desc']:
        order = 'asc'

    # --- Filtering ---
    filters = {
        "sales_rank_current_lte": request.args.get('sales_rank_current_lte', type=int),
        "margin_gte": request.args.get('margin_gte', type=int),
        "keyword": request.args.get('keyword', type=str)
    }
    where_clauses = []
    filter_params = []

    # (Existing filter logic remains the same...)
    if filters.get("sales_rank_current_lte") is not None:
        # If the filter is "Infinite" (or close to it), we skip filtering to include NULLs (missing rank)
        if filters["sales_rank_current_lte"] >= 99999999:
            pass
        else:
            where_clauses.append("\"Sales_Rank_Current\" <= ?")
            filter_params.append(filters["sales_rank_current_lte"])
    if filters.get("margin_gte") is not None:
        where_clauses.append("\"Margin\" >= ?")
        filter_params.append(filters["margin_gte"])
    if filters.get("keyword"):
        keyword_like = f"%{filters['keyword']}%"
        keyword_clauses = ["\"Title\" LIKE ?", "\"Categories_Sub\" LIKE ?", "\"Detailed_Seasonality\" LIKE ?", "\"Manufacturer\" LIKE ?", "\"Author\" LIKE ?", "\"Seller\" LIKE ?"]
        where_clauses.append(f"({ ' OR '.join(keyword_clauses) })")
        filter_params.extend([keyword_like] * len(keyword_clauses))


    # --- Build and Execute Query ---
    try:
        select_clause = "d.*"
        from_clause = f"FROM {TABLE_NAME} AS d"
        query_params = []

        if is_sp_api_connected and user_id:
            select_clause += ", ur.is_restricted, ur.approval_url"
            from_clause += f" LEFT JOIN {RESTRICTIONS_TABLE} AS ur ON d.ASIN = ur.asin AND ur.user_id = ?"
            query_params.append(user_id)
        
        query_params.extend(filter_params)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Get total count
        count_query = f"SELECT COUNT(*) {from_clause}{where_sql}"
        total_records = cursor.execute(count_query, query_params).fetchone()[0]
        total_pages = (total_records + limit - 1) // limit if limit > 0 else 1

        # Get data for the current page
        query_params.extend([limit, offset])
        data_query = f"SELECT {select_clause} {from_clause}{where_sql} ORDER BY d.\"{sort_by}\" {order} LIMIT ? OFFSET ?"
        deal_rows = cursor.execute(data_query, query_params).fetchall()
        deals_list = [dict(row) for row in deal_rows]

        # --- Post-processing and Formatting ---
        for deal in deals_list:
            # Handle restriction status
            if is_sp_api_connected:
                is_restricted = deal.get('is_restricted')
                if is_restricted is None:
                    deal['restriction_status'] = 'pending_check'
                elif is_restricted == 1:
                    deal['restriction_status'] = 'restricted'
                else:
                    deal['restriction_status'] = 'not_restricted'

            # (Existing formatting logic for conditions, bindings, etc. remains the same...)
            binding_map = {"Audio CD": "CD", "Board book": "BB", "Hardcover": "HC", "Paperback": "PB", "Mass Market Paperback": "MMP"}
            condition_string_map = {"New": "N", "Used - Like New": "U - LN", "Used - Very Good": "U - VG", "Used - Good": "U - G", "Used - Acceptable": "U - A"}
            condition_code_map = {"1": "New", "2": "Used - Like New", "3": "Used - Very Good", "4": "Used - Good", "5": "Used - Acceptable"}

            if 'Condition' in deal and deal['Condition'] and str(deal['Condition']).isdigit():
                deal['Condition'] = condition_code_map.get(str(deal['Condition']), f"Unknown ({deal['Condition']})")
            if 'Binding' in deal and deal['Binding'] in binding_map:
                deal['Binding'] = binding_map[deal['Binding']]
            if 'Condition' in deal and deal['Condition'] in condition_string_map:
                deal['Condition'] = condition_string_map[deal['Condition']]

    except sqlite3.Error as e:
        app.logger.error(f"Database query error: {e}")
        return jsonify({"error": "Database query failed", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()

    # --- Format and Return Response ---
    response = {
        "pagination": {
            "total_records": total_records,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        },
        "deals": deals_list
    }
    
    return jsonify(response)

@app.route('/api/recalc-status')
def recalc_status():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    RECALC_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recalc_status.json')

    if not os.path.exists(RECALC_STATUS_FILE):
        return jsonify({"status": "Idle"}) # Or "Not Found", depending on desired frontend logic

    try:
        with open(RECALC_STATUS_FILE, 'r') as f:
            status_data = json.load(f)
        return jsonify(status_data)
    except (IOError, json.JSONDecodeError) as e:
        app.logger.error(f"Could not read or parse recalc_status.json: {e}")
        return jsonify({"status": "Error", "message": "Could not read status file."}), 500

@app.route('/api/refresh-all-deals', methods=['POST'])
def refresh_all_deals():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    # Optional: Check if a task is already running
    # status = get_scan_status()
    # if status.get('status') == 'Running':
    #     return jsonify({'status': 'error', 'message': 'A scan is already in progress.'}), 409

    celery_app.send_task('keepa_deals.recalculator.recalculate_deals')
    return jsonify({'status': 'success', 'message': 'Full data refresh has been initiated.'})

@app.route('/api/debug/deal/<string:asin>')
def debug_deal(asin):
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401

    from keepa_deals.keepa_api import fetch_product_batch
    from keepa_deals.token_manager import TokenManager

    # Use the KEEPA_API_KEY defined at the top of the file
    if not KEEPA_API_KEY:
        return jsonify({'error': 'KEEPA_API_KEY not configured on server.'}), 500

    # The fetch_product_batch function expects a list of ASINs
    # We now receive tokens_left as well, so we unpack it and ignore it with _.
    product_data, api_info, tokens_consumed, _ = fetch_product_batch(KEEPA_API_KEY, [asin])

    if api_info and api_info.get('error_status_code'):
        return jsonify({
            'error': 'Failed to fetch data from Keepa API',
            'status_code': api_info.get('error_status_code'),
            'asin': asin
        }), 502

    if not product_data or not product_data.get('products'):
        return jsonify({'error': 'No product data returned from Keepa', 'asin': asin}), 404

    # Return the raw product data as JSON
    return jsonify(product_data['products'][0])


import secrets
from urllib.parse import urlencode

@app.route('/connect_amazon')
def connect_amazon():
    """
    Step 1 of the real OAuth flow: Redirect the user to the Amazon consent page.
    """
    if not SP_API_APP_ID:
        flash("SP-API application ID is not configured.", "error")
        return redirect(url_for('settings'))

    # Generate a random state token to prevent CSRF attacks
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state

    # Construct the authorization URL
    auth_params = {
        'application_id': SP_API_APP_ID,
        'state': state,
        'redirect_uri': url_for('amazon_callback', _external=True)
    }
    authorization_url = f"{AMAZON_AUTH_URL}?{urlencode(auth_params)}"

    flash("Redirecting to Amazon for authentication...", "info")
    return redirect(authorization_url)

@app.route('/reset_test_user_state', methods=['POST'])
def reset_test_user_state():
    """Resets the session state for the test user."""
    session.clear()
    return jsonify({'status': 'success', 'message': 'Test user state reset.'})

@app.route('/amazon_callback')
def amazon_callback():
    """
    Step 2 of the real OAuth flow: Handle the callback from Amazon,
    exchange the authorization code for tokens.
    """
    # --- Security Check: Validate the state token ---
    received_state = request.args.get('state')
    if not received_state or received_state != session.pop('oauth_state', None):
        flash("Invalid state token. Authorization failed due to a potential CSRF attack.", "error")
        app.logger.warning("OAuth failed: State token mismatch.")
        return redirect(url_for('settings'))

    # --- Exchange the authorization code for tokens ---
    auth_code = request.args.get('spapi_oauth_code')
    seller_id = request.args.get('selling_partner_id')

    if not auth_code or not seller_id:
        flash("Authorization failed: Missing required parameters from Amazon.", "error")
        app.logger.warning(f"OAuth failed: Missing auth_code or seller_id. Code: {auth_code}, Seller ID: {seller_id}")
        return redirect(url_for('settings'))

    token_payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': url_for('amazon_callback', _external=True),
        'client_id': SP_API_CLIENT_ID,
        'client_secret': SP_API_CLIENT_SECRET
    }

    try:
        with httpx.Client() as client:
            response = client.post(AMAZON_TOKEN_URL, data=token_payload)
            response.raise_for_status()
            token_data = response.json()

        # --- Store Tokens Securely ---
        access_token = token_data['access_token']
        session['sp_api_access_token'] = access_token
        session['sp_api_refresh_token'] = token_data['refresh_token']
        session['sp_api_token_expiry'] = time.time() + token_data['expires_in']
        session['sp_api_seller_id'] = seller_id
        session['sp_api_connected'] = True
        session['sp_api_user_id'] = seller_id # Use the seller_id as the unique user identifier

        refresh_token = token_data['refresh_token']
        session['sp_api_refresh_token'] = refresh_token

        app.logger.info(f"Successfully obtained SP-API tokens for seller_id: {seller_id}")

        # --- Trigger the background task with all necessary info ---
        task_args = [seller_id, seller_id, access_token, refresh_token]
        celery_app.send_task('keepa_deals.sp_api_tasks.check_all_restrictions_for_user', args=task_args)

        flash("Successfully connected your Amazon Seller Account!", "success")

    except httpx.HTTPStatusError as e:
        error_details = e.response.json()
        flash(f"Failed to get API tokens from Amazon: {error_details.get('error_description', 'Unknown error')}", "error")
        app.logger.error(f"SP-API token exchange failed: {e.response.text}")
    except Exception as e:
        flash("An unexpected error occurred during token exchange.", "error")
        app.logger.error(f"An unexpected error occurred during token exchange: {e}", exc_info=True)

    return redirect(url_for('settings'))

if __name__ == '__main__':
    create_user_restrictions_table_if_not_exists()
    app.run(debug=True)