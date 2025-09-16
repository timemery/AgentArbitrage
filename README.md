# Agent Arbitrage
Flask app on Hostinger VPS (Ubuntu 22.04) for AI-driven Amazon FBA arbitrage.

- **Root**: https://agentarbitrage.co (renders `templates/index.html` with gradient background)
- **App**: https://agentarbitrage.co/guided_learning (username: `tester`, password: `OnceUponaBurgerTree-12monkeys`)
- **Repo**: https://github.com/timemery/AgentArbitrage
- **Project Plan**: See `Agent Arbitrage Project Plan Draft 1.md` for dev log and project updates.
- **Dev Log**: See `dev-log.md` for detailed session summaries.

## Setup for Development
### Local Development
1. Clone: `git clone https://github.com/timemery/AgentArbitrage.git`
2. Navigate: `cd AgentArbitrage`
3. Create virtual environment: `python3 -m venv venv`
4. Activate: `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
5. Create a `.env` file in the root directory and add your API keys (see Models and APIs section).
6. Install dependencies: `pip install -r requirements.txt`
7. Run: `python wsgi_handler.py`
8. Test: Visit `http://localhost:5000`
9. Develop: Work on `wsgi_handler.py` (Flask app), `templates/` (HTML), `static/` (CSS, images).
10. Push: `git add .`, `git commit -m "Update feature"`, `git push origin main`
- **Note**: `wsgi_handler.py` contains the Flask app; `wsgi.py` is the WSGI entry point for Apache.

## Models and APIs
The project uses several external APIs for its functionality. These require API keys stored in a `.env` file in the project root.

- **Summarization Model**: `facebook/bart-large-cnn` (via Hugging Face API)
- **Strategy Extraction Model**: `grok-4-latest` (via xAI API)
- **YouTube Transcript API**: `youtube-transcript-api` Python library.

### Environment Variables (.env file)
Your `.env` file should contain the following keys:
HF_TOKEN="your_hugging_face_api_key"
XAI_TOKEN="your_xai_api_key"
BRIGHTDATA_USERNAME="your_brightdata_username"
BRIGHTDATA_PASSWORD="your_brightdata_password"
BRIGHTDATA_HOST="your_brightdata_host"
KEEPA_API_KEY="your_keepa_api_key"

- The **Keepa API Key** is required for all deal sourcing and product data analysis.
- The Bright Data credentials are used as a proxy by the `youtube-transcript-api` to prevent getting blocked by YouTube.

## VPS Deployment
1. SSH: `ssh root@your_server_ip`
2. Navigate: `cd /var/www/agentarbitrage`
3. Pull: `git pull origin main`
4. Activate virtual environment: `source venv/bin/activate`
5. Update dependencies: `pip install -r requirements.txt`
6. Apply changes (see below).

### Applying Changes on VPS
**For code changes** (e.g., `wsgi_handler.py`, `wsgi.py`, `templates/`, `static/`):
```
cd /var/www/agentarbitrage
sudo chown -R www-data:www-data /var/www/agentarbitrage
sudo chmod -R 755 /var/www/agentarbitrage
touch wsgi.py
sudo systemctl restart apache2
sudo systemctl status apache2
```

**For Apache configuration changes** (e.g., /etc/apache2/sites-available/agentarbitrage.conf):

```
cd /var/www/agentarbitrage sudo cp agentarbitrage.conf /etc/apache2/sites-available/ sudo a2ensite agentarbitrage.conf sudo apache2ctl configtest sudo systemctl restart apache2 sudo systemctl status apache2
```

**Verify setup**:

- Check logs: sudo tail -n 50 /var/log/apache2/agentarbitrage_error.log, sudo tail -n 50 /var/log/apache2/error.log, sudo tail -n 50 /var/www/agentarbitrage/app.log
- Test site: curl -I [https://localhost](https://localhost/) --insecure, curl [https://localhost](https://localhost/) --insecure
- Test remotely: curl -I [https://agentarbitrage.co](https://agentarbitrage.co/) --insecure, curl [https://agentarbitrage.co](https://agentarbitrage.co/) --insecure
- Browser test: Visit [https://agentarbitrage.co](https://agentarbitrage.co/), log in, submit a YouTube URL (e.g., https://youtu.be/YaF5JRqUm3c), check /results.

## Troubleshooting

- **500 Error (WSGI)**: Ensure `wsgi.py` imports `app` from `wsgi_handler.py` as `application`. Verify `WSGIScriptAlias / /var/www/agentarbitrage/wsgi.py` in `agentarbitrage.conf`.
- **API Failures**: Ensure `HF_TOKEN`, `XAI_TOKEN`, and `BRIGHTDATA_` variables are set correctly in the `.env` file. Check `app.log` for detailed API error messages.
- **Caching/Deployment Issues**: If code changes don’t appear to apply, run `touch wsgi.py` and then `sudo systemctl restart apache2` to force a full reload of the application.
- **Logs**: Always check app.log, agentarbitrage_error.log, and error.log for detailed errors.

## Notes

- The app was renamed from `app.py` to `wsgi_handler.py` to resolve caching issues. Avoid reintroducing `app.py` to prevent configuration conflicts.
- `agentarbitrage.conf` handles both HTTP (redirect to HTTPS) and HTTPS with Let’s Encrypt SSL.
- The `youtube-transcript-api` uses the Bright Data proxy to prevent IP blocking from YouTube. Ensure credentials in `.env` are correct.
- Update `dev-log.md` with summaries of significant changes and debugging sessions.

## API Integration Notes

### Finding the Buy Box Seller ID

A key requirement for evaluating products is to identify the seller who currently holds the Buy Box, especially to determine if the seller is Amazon (`ATVPDKIKX0DER`). Finding this information via the Keepa API proved to be non-trivial.

Our process was as follows:

1. **Initial Approach (Trial and Error):** We initially assumed a top-level `buyBoxSellerId` field would be present in the `/product` endpoint response, as this field name is used in the `/productfinder` query parameters. We implemented a function to extract this field.
2. **Testing and Diagnosis:** Testing revealed this field was consistently empty. This led to the hypothesis that using the `offers=100` parameter in our API calls was altering the response structure, causing this field to be omitted.
3. **External Research:** Further research, aided by the user, pointed towards the [Keepa API Documentation](https://keepaapi.readthedocs.io/en/latest/product_query.html). While this documentation doesn't explicitly name the field for the *current* Buy Box seller ID, it suggests that Buy Box information is embedded within other data structures when using the `offers` parameter. Specifically, Grok's summary indicated the information might be inferred from the `BUY_BOX_SHIPPING` history field.

The current strategy is to use enhanced logging within the application to inspect the raw product data object returned by the API. This will allow us to definitively identify the correct field or combination of fields (such as `buyBoxSellerIdHistory`) needed to extract the current Buy Box seller's ID.

**Last Updated**: August 22, 2025