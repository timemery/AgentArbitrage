import sys
import os
sys.path.insert(0, '/var/www/agentarbitrage')
print(f"Current working directory: {os.getcwd()}", file=open('/tmp/wsgi_cwd.log', 'a'))
from app import app as application