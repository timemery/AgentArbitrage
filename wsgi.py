import sys
import os
import sqlite3

# Monkey-patch sqlite3.connect to set busy_timeout on every connection
_original_connect = sqlite3.connect
def _patched_connect(*args, **kwargs):
    conn = _original_connect(*args, **kwargs)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
sqlite3.connect = _patched_connect

sys.path.insert(0, os.getcwd())
from wsgi_handler import app as application

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000, debug=True)
