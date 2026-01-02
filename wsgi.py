import sys
import os
sys.path.insert(0, os.getcwd())
from wsgi_handler import app as application

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000, debug=True)
