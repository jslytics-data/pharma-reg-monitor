import os
import logging
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

FDA_DMF_URL = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"

# Headers that mimic a real browser to avoid automated blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def fetch_dmf_page_html():
    max_retries = 3
    backoff_factor = 5  # seconds

    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching FDA DMF page from {FDA_DMF_URL} (Attempt {attempt + 1}/{max_retries})")
            response = requests.get(FDA_DMF_URL, headers=HEADERS, timeout=60)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to fetch FDA DMF page on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                sleep_time = backoff_factor * (attempt + 1)
                logging.info(f"Waiting for {sleep_time} seconds before retrying...")
                time.sleep(sleep_time)
            else:
                logging.error(f"All {max_retries} attempts to fetch the FDA DMF page failed.", exc_info=True)
                return None
    return None

def parse_dmf_update_date(html_content: str):
    if not html_content:
        logging.error("Cannot parse empty HTML content.")
        return None

    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        time_tag = soup.select_one("li.node-current-date time")

        if not time_tag:
            logging.warning("Primary selector failed. Trying fallback text search.")
            heading = soup.find('h2', string=lambda t: t and 'Content current as of:' in t.strip())
            if heading:
                time_tag = heading.find_next('time')

        if time_tag:
            date_from_attr = time_tag.get('datetime')
            if date_from_attr:
                return date_from_attr.split('T')[0]
            
            date_from_text = time_tag.get_text(strip=True)
            try:
                return datetime.strptime(date_from_text, '%m/%d/%Y').strftime('%Y-%m-%d')
            except ValueError:
                logging.error(f"Could not parse visible date text: {date_from_text}")
                return None

        logging.error("Structural error: Could not find the DMF update date on the page using any method.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during FDA DMF HTML parsing: {e}", exc_info=True)
        return None

def check_dmf_update_date():
    logging.info("Starting FDA DMF List update date check.")
    html = fetch_dmf_page_html()
    if html is None:
        logging.error("FDA DMF check failed: could not fetch HTML.")
        return None
    
    update_date = parse_dmf_update_date(html)
    if update_date is None:
        logging.error("FDA DMF check failed: could not parse update date.")
        return None

    logging.info(f"FDA DMF check successful. Found update date: {update_date}")
    return update_date

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    latest_update_date = check_dmf_update_date()
    
    if latest_update_date:
        logging.info(f"Test run SUCCESS: Found FDA DMF list update date: {latest_update_date}")
    else:
        logging.error("Test run FAILED: The check_dmf_update_date function returned a failure signal (None).")