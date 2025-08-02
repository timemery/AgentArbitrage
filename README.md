# Agent Arbitrage
Flask app on Hostinger VPS (Ubuntu 22.04) for AI-driven Amazon FBA arbitrage.
- Root: https://agentarbitrage.co (public index.html)
- App: https://agentarbitrage.co/app (username: tester, password: OnceUponaBurgerTree-12monkeys)
- Repo: https://github.com/timemery/AgentArbitrage
- Project Plan: See `Agent Arbitrage Project Plan Draft 1.md`

## Setup for Development
ssh jules@31.97.11.61
cd /var/www/agentarbitrage
git pull origin main
sudo cp agentarbitrage.conf /etc/apache2/sites-available/
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart apache2
