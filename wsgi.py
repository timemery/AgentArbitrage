import sys
import os

# Add the project directory to the system path to allow for imports
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app object from our handler file
from wsgi_handler import app as application
