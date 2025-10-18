# Keepa Deals API
Jules collaboration on Keepa Deals.
- (Last update: Version 5)

## Overview
This codebase includes scripts (`Keepa_Deals.py`, `stable_products.py`, etc.) to fetch and process Keepa API data, outputting `Keepa_Deals_Export.csv`.

## Environment
- Virtualenv: `~/keepa_api/keepa-deals/venv` (or user-specific path)
- Python: 3.10.17
- Dependencies: See `requirements.txt`
- Config: `config.json` (API key)

## Rules
- Maintain chunk markers (e.g., `# Chunk X starts/ends`) in Python files for modular updates.
- Preserve all field-order comments (e.g., `# Percent Down 90`, `# Author starts/ends`) in Python files. These are critical for tracking yet-to-be-solved fields and ensuring their correct order in the CSV file (216 columns). Do not remove or modify these comments.
- No auto-updates to dependencies or Python for stability.
- Output: `Keepa_Deals_Export.csv` (216 columns, e.g., Title, ASIN, Used Offer Count - Current).

## Setup
### Python Version
- Standard: Python 3.10.17
- Note: Python 3.10.17 ensures compatibility with the Keepa API and dependencies.

### Setup Instructions
1. Create a project directory and virtual environment:
   mkdir -p ~/keepa_api/keepa-deals
   cd ~/keepa_api/keepa-deals
   python3 -m venv venv
   source venv/bin/activate
2. Clone the repository:
   git clone https://github.com/timemery/keepa-deals.git .
3. WARNING: Do NOT install anything in /home/jules/.local/ for this project; use only the virtual environment (venv).
4. Install dependencies in the virtual environment:
   pip install -r requirements.txt
   deactivate

### Expected outputs (when running Keepa_Deals.py): 
- **Keepa_Deals_Export.csv**
- **debug_log.txt**

### Dependencies
See `requirements.txt` for the full list. Key notes:
- `keepa==1.3.5`: Included for compatibility with existing code. Do not use the Keepa Python client for API calls. Instead, use the `requests` library to make direct HTTP requests to `https://api.keepa.com` (e.g., `requests.get()` with the API key from `config.json`).
- Other dependencies: `pandas`, `numpy`, `requests`, etc., for data processing and HTTP requests.

## Development Setup
- **Editor**: Sublime Text for editing.
- **Version Control**: GitHub Desktop for commits.
- **Environment**: Python 3.10.17 in a virtual environment (e.g., `~/keepa_api/keepa-deals/venv`). Project files: `~/keepa_api/keepa-deals/`.
- **Execution**: Activate virtual environment, install dependencies, run `python3 Keepa_Deals.py --no-cache`.

## Project Structure
- `AGENTS.md`: Reference to provide persistent instructions for consultation throughout the project. 
- `Keepa_Documentation-official.md`: Most current and complete documentation for Keepa API
- `SOW.txt`: Scope of Work.
- `Keepa_Deals.py`: Main script for fetching deals and writing CSV.
- `stable_products.py`: Defines product conditions (e.g., used_good, used_like_new).
- `stable_deals.py`: Handles deal logic (e.g., Percent Down 90).
- `stable_calculations.py`: Isolates calculated fields (e.g., Percent Down 90).
- `field_mappings.py`: Maps CSV headers to functions (FUNCTION_LIST).
- `headers.json`: Defines 216 CSV column headers or mappings.
- `config.json`: Contains the Keepa API key.
- `requirements.txt`: Lists dependencies (requests, retrying, pandas, pytz).
- `README.md`: Project documentation.
- `Keepa_Deals_Export.csv`: Output file for deal data.
- `debug_log.txt`: Debug logs (e.g., stats.current).
- `API_Dev_Log.txt`: Development log.