import os
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

FDA_DMF_URL = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"

def fetch_dmf_page_html():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"Fetching FDA DMF page from {FDA_DMF_URL}")
        response = requests.get(FDA_DMF_URL, headers=headers, timeout=60)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch FDA DMF page: {e}")
        return None

def parse_dmf_update_date(html_content: str):
    if not html_content:
        logging.warning("FDA DMF HTML content is empty, cannot parse.")
        return None

    soup = BeautifulSoup(html_content, 'lxml')
    time_tag = None

    # Primary Strategy: Use a specific CSS selector for efficiency
    time_tag = soup.select_one("li.node-current-date time")

    # Fallback Strategy: Find the heading text for robustness
    if not time_tag:
        logging.warning("Primary selector failed. Trying fallback text search.")
        heading = soup.find('h2', string=lambda t: t and 'Content current as of:' in t.strip())
        if heading:
            time_tag = heading.find_next('time')

    if time_tag:
        # Prioritize the machine-readable 'datetime' attribute
        date_from_attr = time_tag.get('datetime')
        if date_from_attr:
            # Format to YYYY-MM-DD
            return date_from_attr.split('T')[0]
        
        # If attribute is missing, fall back to the visible text
        date_from_text = time_tag.get_text(strip=True)
        try:
            # Attempt to parse MM/DD/YYYY format
            return datetime.strptime(date_from_text, '%m/%d/%Y').strftime('%Y-%m-%d')
        except ValueError:
            logging.error(f"Could not parse visible date text: {date_from_text}")
            return None

    logging.error("Could not find the DMF update date on the page using any method.")
    return None

def check_dmf_update_date():
    logging.info("Checking for FDA DMF List update date.")
    html = fetch_dmf_page_html()
    if not html:
        return None
    
    update_date = parse_dmf_update_date(html)
    return update_date

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    latest_update_date = check_dmf_update_date()
    
    if latest_update_date:
        logging.info(f"SUCCESS: Found FDA DMF list update date: {latest_update_date}")
    else:
        logging.error("FAILURE: Could not retrieve the FDA DMF list update date.")