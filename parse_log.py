#!/usr/bin/env python3
import json
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOG_FILE = 'diag_output.txt'
OUTPUT_FILE = 'extracted_log.json'

def extract_json_from_log():
    """
    Parses a large log file to extract specific JSON blocks, cleans them,
    and saves them to a new file.
    """
    logger.info(f"Attempting to extract data from '{LOG_FILE}'...")

    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            log_content = f.read()
    except FileNotFoundError:
        logger.error(f"Error: The input file named '{LOG_FILE}' was not found. Please ensure the terminal output was saved to this file.")
        return

    # Regex to find the JSON blocks, accounting for the logger prefix on each line
    product_match = re.search(r'--- RAW PRODUCT DATA ---\n(.*?)--- END RAW PRODUCT DATA ---', log_content, re.DOTALL)
    final_row_match = re.search(r'--- FINAL PROCESSED ROW ---\n(.*?)--- END FINAL PROCESSED ROW ---', log_content, re.DOTALL)

    if not product_match:
        logger.error("Could not find '--- RAW PRODUCT DATA ---' block in the log file.")
        return
    if not final_row_match:
        logger.error("Could not find '--- FINAL PROCESSED ROW ---' block in the log file.")
        return

    # Clean the captured strings
    def clean_json_string(match_group):
        lines = match_group.strip().split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove the logging prefix (e.g., "2025-11-19 17:56:55,814 - INFO - ")
            cleaned_line = re.sub(r'^.*? - INFO - ', '', line)
            cleaned_lines.append(cleaned_line)
        return ''.join(cleaned_lines)

    product_json_str = clean_json_string(product_match.group(1))
    final_row_json_str = clean_json_string(final_row_match.group(1))

    try:
        product_data = json.loads(product_json_str)
        final_row_data = json.loads(final_row_json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON. This may be due to an incomplete log capture. Error: {e}")
        # Optionally, log the problematic strings for debugging
        # logger.debug("Problematic product_json_str:\n" + product_json_str)
        # logger.debug("Problematic final_row_json_str:\n" + final_row_json_str)
        return

    # Consolidate the essential data we need for analysis
    extracted_data = {
        'asin': product_data.get('asin'),
        'offers': product_data.get('offers'),
        'stats': product_data.get('stats'),
        'final_processed_row': final_row_data
    }

    try:
        with open(OUTPUT_FILE, 'w') as out_f:
            json.dump(extracted_data, out_f, indent=4)
        logger.info(f"Successfully extracted key information to '{OUTPUT_FILE}'")
    except Exception as e:
        logger.error(f"An error occurred while writing the output file: {e}")

if __name__ == "__main__":
    extract_json_from_log()
