from flask import Flask
import logging
import os

# --- CONFIGURE LOGGING FIRST ---
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
# --- END LOGGING CONFIG ---

logging.info("--- MINIMAL wsgi_handler.py starting up ---")

app = Flask(__name__)
application = app

@app.route('/')
def index():
    return 'Minimal wsgi_handler.py is working!'
