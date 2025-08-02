# Agent Arbitrage

This project is an autonomous AI agent that identifies high-profit books for Amazon FBA arbitrage.

## Project Plan

The project is divided into two phases:

*   **Phase 1A: AI Agent Development (Weeks 1-6)**
*   **Phase 1B: Web Interface and Refinement (Weeks 7-10)

A more detailed project plan can be found in the `Agent_Arbitrage - Jules_Grok.md` file.

## Server Information

*   **VPS Provider**: Hostinger
*   **OS**: Ubuntu 22.04
*   **IP Address**: `31.97.11.61`
*   **SSH Access**: `ssh root@31.97.11.61`

## Deployment

The application is a Flask web application served by Apache with `mod_wsgi`.

### 1. Clone the Repository

```bash
git clone https://github.com/timemery/AgentArbitrage.git
```

### 2. Set up the Python Environment

The project uses a Python virtual environment.

```bash
cd /var/www/agentarbitrage
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Application Files

**app.py**
```python
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=True)
```

**wsgi.py**
```python
import sys
sys.path.insert(0, '/var/www/agentarbitrage')
from app import app as application
```

### 5. Configure Apache

**`/etc/apache2/sites-available/agentarbitrage.conf`**
```apache
<VirtualHost *:80>
    ServerName agentarbitrage.co
    ServerAlias www.agentarbitrage.co
    WSGIScriptAlias / /var/www/agentarbitrage/wsgi.py
    <Directory /var/www/agentarbitrage>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    ErrorLog ${APACHE_LOG_DIR}/agentarbitrage_error.log
    CustomLog ${APACHE_LOG_DIR}/agentarbitrage_access.log combined
</VirtualHost>
```

**`/etc/apache2/sites-available/agentarbitrage-le-ssl.conf`**
```apache
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName agentarbitrage.co
    ServerAlias www.agentarbitrage.co
    WSGIScriptAlias / /var/www/agentarbitrage/wsgi.py
    <Directory /var/www/agentarbitrage>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    WSGIDaemonProcess agentarbitrage python-home=/var/www/agentarbitrage/venv python-path=/var/www/agentarbitrage
    WSGIProcessGroup agentarbitrage
    ErrorLog ${APACHE_LOG_DIR}/agentarbitrage_error.log
    CustomLog ${APACHE_LOG_DIR}/agentarbitrage_access.log combined
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/agentarbitrage.co/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/agentarbitrage.co/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
```

### 6. Restart Apache

```bash
sudo systemctl restart apache2
```
