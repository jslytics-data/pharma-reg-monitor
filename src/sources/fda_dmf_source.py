import os
import json
import logging
import time
import re
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
FDA_DMF_URL = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"
FDA_BASE_URL = "https://www.fda.gov"

# Standard browser headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# --- HELPER: CHALLENGE SOLVER ---
def _compute_sha256(text: str) -> str:
    """Mimics the JS SHA256 function found in FDA's abuse deterrent script."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest().upper()

def _solve_challenge_and_get_session() -> requests.Session | None:
    """
    Initiates a session. If the FDA 'abuse-deterrent' challenge is detected,
    it solves the math puzzle, sets cookies, and authorizes the session.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        logging.info(f"Initiating handshake with FDA DMF Page...")
        response = session.get(FDA_DMF_URL, timeout=30)

        # Case A: No challenge (200 OK and clean HTML)
        if response.status_code == 200 and "abuse-deterrent.js" not in response.text:
            logging.info("No challenge detected. Session is ready.")
            return session

        # Case B: Challenge Detected
        if "abuse-deterrent.js" in response.text or "public_salt" in response.text:
            logging.info("Abuse deterrent challenge detected. Attempting to solve...")

            # Extract variables
            salt_match = re.search(r'let public_salt = "([^"]+)";', response.text)
            candidates_match = re.search(r'candidates = "([^"]+)".split', response.text)

            if not salt_match or not candidates_match:
                logging.error("Could not extract challenge variables from HTML.")
                return None

            public_salt = salt_match.group(1)
            candidates = candidates_match.group(1).split('/')

            # Solve puzzle
            auth_1 = _compute_sha256(public_salt + candidates[0])
            auth_2 = _compute_sha256(public_salt + candidates[1])

            # Set cookies on the domain
            domain = urlparse(FDA_DMF_URL).netloc
            session.cookies.set("authorization_1", auth_1, domain=domain)
            session.cookies.set("authorization_2", auth_2, domain=domain)

            logging.info("Challenge solved. Authorization cookies set.")
            return session
        
        logging.warning(f"Unexpected response: {response.status_code}")
        return None

    except Exception as e:
        logging.error(f"Error during session initialization: {e}", exc_info=True)
        return None

def parse_dmf_page_details(html_content: str):
    if not html_content:
        logging.error("Cannot parse empty HTML content.")
        return None

    try:
        # Use html.parser for stability in Cloud Run
        soup = BeautifulSoup(html_content, 'html.parser')
        details = {}

        # 1. Extract Update Date
        # Selector: li.node-current-date time
        # We look for a <time> tag inside an <li> with that class
        date_container = soup.find('li', class_='node-current-date')
        time_tag = date_container.find('time') if date_container else None
        
        if time_tag and time_tag.has_attr('datetime'):
            details['update_date'] = time_tag['datetime'].split('T')[0]
        else:
            # Fallback: Try to find date text in the header area
            logging.warning("Could not find standard 'node-current-date' time tag. Attempting fallback...")
            # (Optional: Add fallback logic here if needed, currently sticking to standard)
            return None

        # 2. Extract Excel Download Link
        # Look for <a> containing text 'excel' (case insensitive)
        excel_link_tag = soup.find('a', string=lambda text: text and 'excel' in text.lower())
        
        if excel_link_tag and excel_link_tag.has_attr('href'):
            href = excel_link_tag['href']
            if href.startswith("http"):
                details['download_url'] = href
            else:
                details['download_url'] = f"{FDA_BASE_URL}{href}"
        else:
            logging.error("Structural error: Could not find the Excel download link on the page.")
            return None

        return details
    except Exception as e:
        logging.error(f"An unexpected error occurred during FDA DMF HTML parsing: {e}", exc_info=True)
        return None

def check_dmf_details():
    logging.info("Starting FDA DMF List details check.")
    
    # 1. Get Authorized Session
    session = _solve_challenge_and_get_session()
    if not session:
        logging.error("FDA DMF check failed: Could not initialize authorized session.")
        return None

    # 2. Fetch Page
    try:
        logging.info("Fetching FDA DMF page content...")
        response = session.get(FDA_DMF_URL, timeout=60)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        logging.error(f"FDA DMF check failed during fetch: {e}")
        return None

    # 3. Parse
    details = parse_dmf_page_details(html_content)
    if details is None:
        logging.error("FDA DMF check failed: could not parse page details.")
        return None

    logging.info(f"FDA DMF check successful. Found details: {details}")
    return details

if __name__ == "__main__":
    # CLI Test Block
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