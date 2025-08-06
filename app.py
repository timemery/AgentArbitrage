from flask import Flask, render_template, request, redirect, url_for, session
import httpx
from bs4 import BeautifulSoup
import re
import json

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # It's important to set a secret key for sessions

# --- Hugging Face API Configuration ---
# Replace with your actual Hugging Face API key
HUGGING_FACE_API_KEY = "placeholder"
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

def query_huggingface_api(payload):
    headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}
    with httpx.Client() as client:
        response = client.post(API_URL, headers=headers, json=payload)
        return response.json()

def chunk_text(text, chunk_size=1024):
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

@app.route('/app', methods=['GET', 'POST'])
def main_app():
    if request.method == 'POST':
        # This is for the login form
        username = request.form.get('username')
        password = request.form.get('password')
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('main_app'))
        else:
            return 'Invalid credentials', 401
    
    if session.get('logged_in'):
        return render_template('guided_learning.html')
    else:
        # This handles GET requests to /app without being logged in
        return redirect(url_for('index'))

@app.route('/learn', methods=['POST'])
def learn():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    # Clear previous results from the session
    session.pop('original_input', None)
    session.pop('scraped_text', None)
    session.pop('summary', None)
    
    print("Inside learn route")
    print(f"Request form: {request.form}")
    if 'learning_text' in request.form:
        learning_text = request.form['learning_text']
        print(f"Received learning text: {learning_text}")
        session['original_input'] = learning_text
        print(f"Session original_input set to: {session['original_input']}")
    else:
        print("learning_text not in request.form")
        learning_text = ""
        session['original_input'] = ""
    
    # Check if the input is a URL
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
                session['scraped_text'] = scraped_text
        except httpx.HTTPStatusError as e:
            session['scraped_text'] = f"Error scraping URL: {e.response.status_code} {e.response.reason_phrase} for url: {e.request.url}"
            return redirect(url_for('results'))
        except httpx.RequestError as e:
            session['scraped_text'] = f"Error scraping URL: {e}"
            return redirect(url_for('results'))
    else:
        session['scraped_text'] = learning_text

    # Summarize the text
    print("Starting summarization...")
    try:
        scraped_text = session.get('scraped_text', '')
        print(f"Text to summarize: {scraped_text}")
        if len(scraped_text) > 1024:
            print("Text is long, chunking...")
            text_chunks = chunk_text(scraped_text)
            summaries = []
            for i, chunk in enumerate(text_chunks):
                print(f"Summarizing chunk {i+1}/{len(text_chunks)}")
                print(f"Chunk content: {chunk}")
                summary_payload = {"inputs": chunk, "parameters": {"min_length": 30, "max_length": 150}}
                summary_data = query_huggingface_api(summary_payload)
                print(f"API response for chunk {i+1}: {summary_data}")
                if isinstance(summary_data, list) and summary_data and 'summary_text' in summary_data[0]:
                    summaries.append(summary_data[0]['summary_text'])
                else:
                    print(f"Could not summarize chunk {i+1}. API response: {summary_data}")
        if summaries:
            session['summary'] = "\n".join(summaries)
        else:
            session['summary'] = "Could not generate a summary."
    elif scraped_text:
        print("Text is short, summarizing directly...")
        summary_payload = {"inputs": scraped_text, "parameters": {"min_length": 30, "max_length": 150}}
        summary_data = query_huggingface_api(summary_payload)
        print(f"API response: {summary_data}")
        if isinstance(summary_data, list) and summary_data and 'summary_text' in summary_data[0]:
            session['summary'] = summary_data[0]['summary_text']
        else:
            print(f"Could not summarize text. API response: {summary_data}")
            session['summary'] = "Could not summarize the text."
    except Exception as e:
        print(f"An error occurred during summarization: {e}")
        session['summary'] = "An error occurred during summarization."
    print("Summarization finished.")

    return redirect(url_for('results'))

@app.route('/results')
def results():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('results.html')

@app.route('/approve', methods=['POST'])
def approve():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    approved_rules = request.form.get('approved_rules')
    print("Approved rules:")
    print(approved_rules)
    
    # For now, just redirect back to the main app page
    return redirect(url_for('main_app'))

from flask import flash

@app.route('/clear_session')
def clear_session():
    session.pop('original_input', None)
    session.pop('scraped_text', None)
    session.pop('summary', None)
    flash('Session cleared!', 'success')
    return redirect(url_for('main_app'))

@app.route('/test_route', methods=['POST'])
def test_route():
    print("Test route called!")
    return "Test route called!"

if __name__ == '__main__':
    app.run(debug=True)
