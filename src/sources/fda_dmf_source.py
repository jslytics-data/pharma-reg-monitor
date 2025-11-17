import os
import json
import logging
import time
from datetime import datetime

from curl_cffi import requests
from bs4 import BeautifulSoup

FDA_DMF_URL = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"
FDA_BASE_URL = "https://www.fda.gov"

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
    backoff_factor = 5

    # Use a session object to better mimic a real browser session
    with requests.Session() as session:
        session.headers.update(HEADERS)

        for attempt in range(max_retries):
            try:
                logging.info(f"Fetching FDA DMF page from {FDA_DMF_URL} (Attempt {attempt + 1}/{max_retries})")
                # Use the session to make the request, with browser impersonation
                response = session.get(FDA_DMF_URL, timeout=60, impersonate="chrome110")
                response.raise_for_status()
                return response.text
            except requests.errors.RequestsError as e:
                logging.warning(f"Failed to fetch FDA DMF page on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor * (attempt + 1)
                    logging.info(f"Waiting for {sleep_time} seconds before retrying...")
                    time.sleep(sleep_time)
                else:
                    logging.error(f"All {max_retries} attempts to fetch the FDA DMF page failed.", exc_info=True)
                    return None
    return None

def parse_dmf_page_details(html_content: str):
    if not html_content:
        logging.error("Cannot parse empty HTML content.")
        return None

    try:
        soup = BeautifulSoup(html_content, 'lxml')
        details = {}

        time_tag = soup.select_one("li.node-current-date time")
        if time_tag and time_tag.get('datetime'):
            details['update_date'] = time_tag.get('datetime').split('T')[0]
        else:
            logging.error("Structural error: Could not find the DMF update date on the page.")
            return None

        excel_link_tag = soup.find('a', string=lambda text: text and 'excel' in text.lower())
        if excel_link_tag and excel_link_tag.get('href'):
            relative_url = excel_link_tag.get('href')
            details['download_url'] = f"{FDA_BASE_URL}{relative_url}"
        else:
            logging.error("Structural error: Could not find the Excel download link on the page.")
            return None

        return details
    except Exception as e:
        logging.error(f"An unexpected error occurred during FDA DMF HTML parsing: {e}", exc_info=True)
        return None

def check_dmf_details():
    logging.info("Starting FDA DMF List details check.")
    html = fetch_dmf_page_html()
    if html is None:
        logging.error("FDA DMF check failed: could not fetch HTML.")
        return None

    details = parse_dmf_page_details(html)
    if details is None:
        logging.error("FDA DMF check failed: could not parse page details.")
        return None

    logging.info(f"FDA DMF check successful. Found details: {details}")
    return details

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    dmf_details = check_dmf_details()

    if dmf_details:
        logging.info(f"Test run SUCCESS: Found FDA DMF details.")
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fda_dmf_details_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dmf_details, f, indent=4)

        logging.info(f"Saved details to {filepath}")
    else:
        logging.error("Test run FAILED: The function returned a failure signal (None).")