# Agent Arbitrage
Flask app on Hostinger VPS (Ubuntu 22.04) for AI-driven Amazon FBA arbitrage.

- **Root**: https://agentarbitrage.co (renders `templates/index.html` with gradient background)
- **App**: https://agentarbitrage.co/guided_learning (username: `tester`, password: `OnceUponaBurgerTree-12monkeys`)
- **Repo**: https://github.com/timemery/AgentArbitrage
- **Project Plan**: See `Agent_Arbitrage_-_Jules_Grok.md` for dev log and project updates

## Setup for Development
### Local Development
1. Clone: `git clone https://github.com/timemery/AgentArbitrage.git`
2. Navigate: `cd AgentArbitrage`
3. Create virtual environment: `python3 -m venv venv`
4. Activate: `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
5. Install dependencies: `pip install -r requirements.txt`
6. Run: `python wsgi_handler.py`
7. Test: Visit `http://localhost:5000`
8. Develop: Work on `wsgi_handler.py` (Flask app), `templates/` (HTML), `static/` (CSS, images)
9. Push: `git add .`, `git commit -m "Update feature"`, `git push origin main`
- **Note**: Place images in `static` folder, reference as `/static/filename.jpg` in HTML.
- **Note**: `wsgi_handler.py` contains the Flask app; `wsgi.py` is the WSGI entry point for Apache.

## Models and APIs
The project uses Hugging Face and xAI APIs for AI capabilities.

- **Summarization Model**: `facebook/bart-large-cnn` (Hugging Face)
- **Strategy Extraction Model**: `grok-4-latest` (xAI, primary); `facebook/bart-large-cnn` (Hugging Face, fallback)
- **Hugging Face API**: Requires `HF_TOKEN` in `/var/www/agentarbitrage/.env`. A **Pro subscription** is recommended to avoid rate limits and model loading delays.
- **xAI API**: Requires `XAI_TOKEN` in `.env` for strategy extraction.
- **Selenium for YouTube Scraping**: Uses ChromeDriver (`/usr/local/bin/chromedriver`) and Google Chrome. Bright Data proxy credentials (`BRIGHTDATA_USERNAME`, `BRIGHTDATA_PASSWORD`, `BRIGHTDATA_HOST`, `BRIGHTDATA_PORT`) in `.env` are optional for scraping reliability.

## VPS Deployment
1. SSH: `ssh root@31.97.11.61`
2. Navigate: `cd /var/www/agentarbitrage`
3. Pull: `git pull origin main`
4. Activate virtual environment: `source venv/bin/activate`
5. Update dependencies: `pip install -r requirements.txt`
6. Apply changes (see below).

### Applying Changes on VPS
**For code changes** (e.g., `wsgi_handler.py`, `wsgi.py`, `templates/`, `static/`):
```bash
cd /var/www/agentarbitrage
sudo chown -R www-data:www-data /var/www/agentarbitrage
sudo chmod -R 755 /var/www/agentarbitrage
touch wsgi.py
sudo systemctl restart apache2
sudo systemctl status apache2
```

**For Apache configuration changes** (e.g., /etc/apache2/sites-available/agentarbitrage.conf):

bash

```
cd /var/www/agentarbitrage sudo cp agentarbitrage.conf /etc/apache2/sites-available/ sudo a2ensite agentarbitrage.conf sudo apache2ctl configtest sudo systemctl restart apache2 sudo systemctl status apache2
```

**Verify setup**:

- Check logs: sudo tail -n 50 /var/log/apache2/agentarbitrage_error.log, sudo tail -n 50 /var/log/apache2/error.log, sudo tail -n 50 /var/www/agentarbitrage/app.log
- Test site: curl -I https://localhost --insecure, curl https://localhost --insecure
- Test remotely: curl -I https://agentarbitrage.co --insecure, curl https://agentarbitrage.co --insecure
- Browser test: Visit https://agentarbitrage.co, log in, submit a YouTube URL (e.g., https://youtu.be/YaF5JRqUm3c), check /results.

## Troubleshooting

- **500 Error (WSGI)**: Ensure wsgi.py imports app from wsgi_handler.py as application. Verify WSGIScriptAlias / /var/www/agentarbitrage/wsgi.py in agentarbitrage.conf.

- ChromeDriver Errors

  : If 

  /results

   shows 

  Service /usr/local/bin/chromedriver unexpectedly exited

  :

  - Verify ChromeDriver: /usr/local/bin/chromedriver --version
  - Verify Chrome: google-chrome --version
  - Ensure compatibility between Chrome and ChromeDriver versions.
  - Check permissions: ls -l /usr/local/bin/chromedriver, sudo chmod +x /usr/local/bin/chromedriver
  - Test ChromeDriver: /usr/local/bin/chromedriver
  - Check .env for Bright Data proxy credentials if YouTube scraping fails.

- **API Failures**: Ensure HF_TOKEN and XAI_TOKEN are set in .env. Check logs for API errors (app.log).

- **Caching Issues**: If changes don’t apply, touch wsgi.py (touch wsgi.py) and restart Apache.

- **Logs**: Always check app.log, agentarbitrage_error.log, and error.log for detailed errors.

## Notes

- The app was renamed from app.py to wsgi_handler.py to resolve caching issues. Avoid reintroducing app.py to prevent configuration conflicts.
- agentarbitrage.conf handles both HTTP (redirect to HTTPS) and HTTPS with Let’s Encrypt SSL.
- ChromeDriver issues may require Bright Data proxy for reliable YouTube scraping.
- Update Agent_Arbitrage_-_Jules_Grok.md with dev log entries for all changes and issues.

**Last Updated**: August 20, 2025


