# Agent Arbitrage
Flask app on Hostinger VPS (Ubuntu 22.04) for AI-driven Amazon FBA arbitrage.
- Root: https://agentarbitrage.co (renders templates/index.html with AIGIRL.jpg background)
- App: https://agentarbitrage.co/guided_learning (username: tester, password: OnceUponaBurgerTree-12monkeys)
- Repo: https://github.com/timemery/AgentArbitrage
- Project Plan: See `Agent Arbitrage Project Plan Draft 1.md`

## Setup for Development
### Local Development (Jules)
1. Clone: `git clone https://github.com/timemery/AgentArbitrage.git`
2. Navigate: `cd AgentArbitrage`
3. Create virtual environment: `python3 -m venv venv`
4. Activate: `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
5. Install dependencies: `pip install -r requirements.txt`
6. Run: `python app.py`
7. Test: Visit `http://localhost:5000`
8. Develop Guided Learning (URL scraping, Hugging Face API)
9. Push: `git add .`, `git commit -m "Update Guided Learning"`, `git push origin main`
- Note: Place images in `static` folder, reference as `/static/filename.jpg` in HTML.

## Models and API

This project relies on the Hugging Face API for its AI capabilities.

*   **Summarization Model:** `facebook/bart-large-cnn`
*   **Strategy Extraction Model:** `google/flan-t5-large` (previously attempted `mistralai/Mistral-7B-Instruct-v0.1`)

**Subscription:** A Hugging Face **Pro subscription** is recommended to ensure the stability and performance of the API calls and to avoid rate limits or "model loading" delays.


### VPS Deployment (Tim)
1. SSH: `ssh root@31.97.11.61`
2. Navigate: `cd /var/www/agentarbitrage`
3. Pull: `git pull origin main`
4. Update dependencies: `source venv/bin/activate`, `pip install -r requirements.txt`
5. Apply changes (see below).

#### Applying Changes on VPS
**For most changes** (e.g., `app.py`, `templates/index.html`, `templates/guided_learning.html`, `static/AIGIRL.jpg`):
```bash
cd /var/www/agentarbitrage
sudo chown -R www-data:www-data /var/www/agentarbitrage
sudo chmod -R 755 /var/www/agentarbitrage
touch wsgi.py
sudo systemctl restart apache2
sudo systemctl status apache2
For Apache configuration changes (e.g., agentarbitrage.conf, agentarbitrage-le-ssl.conf):

cd /var/www/agentarbitrage
sudo cp agentarbitrage.conf /etc/apache2/sites-available/
sudo cp agentarbitrage-le-ssl.conf /etc/apache2/sites-available/
sudo a2ensite agentarbitrage.conf
sudo a2ensite agentarbitrage-le-ssl.conf
sudo systemctl restart apache2
sudo systemctl status apache2
