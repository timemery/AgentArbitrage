# Agent Arbitrage

An AI-driven Flask application for Amazon FBA arbitrage, deployed on a Hostinger VPS (Ubuntu 22.04).

- **Public URL**: https://agentarbitrage.co
- **Dashboard**: https://agentarbitrage.co/dashboard
- **Guided Learning**: https://agentarbitrage.co/guided_learning
- **Login**: `tester` / `OnceUponaBurgerTree-12monkeys`

## Key Features

- **Deals Dashboard**: Real-time arbitrage opportunities with advanced filtering and "Janitor" cleanup. (User Access)
- **Settings**: Configure business costs, fees, and API credentials. (User Access)
- **Guided Learning**: Teach the agent by feeding it YouTube videos or articles. It extracts strategies and mental models using xAI. (Admin Only)
- **Agent Brain & Strategies**: Repositories of the AI's learned knowledge. (Admin Only)
- **Data Sourcing / Deals Config**: Configurable Keepa scanning engine. (Admin Only)

## User Roles & Access Control

The application uses a role-based permission system:

*   **User Role**: Restricted to the **Dashboard** and **Settings** only. Focused on finding and analyzing deals.
*   **Admin Role**: Full access to all features, including **Strategies**, **Guided Learning**, **Agent Brain**, and **Deals Configuration**.

---

## CRITICAL WARNINGS FOR AGENTS

1.  **DO NOT READ CELERY LOGS:** Never generate or read `celery.log` or similar large log files. Doing so will crash your environment and terminate the task. Verification must be done through other means (e.g., `check_db.py`).
2.  **ENVIRONMENT SEPARATION:** Your sandboxed environment is completely isolated from the user's server (`/var/www/agentarbitrage`). Do not reference your internal file paths. All commands are executed on the user's server.

---

## Getting Started (Local Development)

1.  **Clone the Repository:**
    `git clone https://github.com/timemery/AgentArbitrage.git`
2.  **Navigate to Directory:**
    `cd AgentArbitrage`
3.  **Create & Activate Virtual Environment:**
    `python3 -m venv venv`
    `source venv/bin/activate`
4.  **Install Dependencies:**
    `pip install -r requirements.txt`
5.  **Create `.env` File:** Create a `.env` file in the root directory and add your API keys (see Core Technologies section below).
6.  **Run the Application:**
    `python wsgi_handler.py`
7.  **Access:**
    Open `http://localhost:5000` in your browser.

---

## Core Technologies & APIs

This project relies on several external APIs. Keys must be stored in a `.env` file in the project root.

**Required `.env` Variables:**
```
HF_TOKEN="your_hugging_face_api_key"
XAI_TOKEN="your_xai_api_key"
BRIGHTDATA_USERNAME="your_brightdata_username"
BRIGHTDATA_PASSWORD="your_brightdata_password"
BRIGHTDATA_HOST="your_brightdata_host"
KEEPA_API_KEY="your_keepa_api_key"
```
- **Keepa API:** The core service for all deal sourcing and product data analysis.
- **Bright Data:** Used as a proxy for the `youtube-transcript-api` to prevent blocking.

---

## Deployment (Production VPS)

1.  **SSH into Server:**
    `ssh root@your_server_ip`
2.  **Navigate to App Directory:**
    `cd /var/www/agentarbitrage`
3.  **Pull Latest Changes:**
    `git pull origin main`
4.  **Update Dependencies:**
    `source venv/bin/activate`
    `pip install -r requirements.txt`
5.  **Apply and Restart:** To apply code changes and restart the application, run the `touch` command on the WSGI entry point and restart Apache:
    ```bash
    touch wsgi.py
    sudo systemctl restart apache2
    ```
---

## Troubleshooting

- **500 Internal Server Error:** Often a WSGI configuration issue. Ensure `wsgi.py` correctly imports the `app` instance from `wsgi_handler.py`. Check Apache logs for details: `/var/log/apache2/agentarbitrage_error.log`.
- **API Failures:** Verify that all required keys in your `.env` file are correct. Check `app.log` for specific API error messages.
- **Changes Not Applying:** If new code doesn't seem to be running, force a full application reload with `touch wsgi.py` followed by `sudo systemctl restart apache2`.

---

## Architectural Notes

- **Primary Application File:** The main Flask application logic is in `wsgi_handler.py`. The `wsgi.py` file is the entry point for the Apache/mod_wsgi server.
- **Documentation & Logs:** Key project documents, architectural discussions, and historical dev logs are stored in the `/Documents_Dev_Logs` folder.
- **Reference Code:** Older versions of the codebase are available for reference in `/keepa_deals_reference` and `/AgentArbitrage-before_persistent_db`.

*Last Updated: October 12, 2025*
