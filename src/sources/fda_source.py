import os
import json
import logging
import time
import re
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
FDA_AJAX_URL = "https://www.fda.gov/datatables/views/ajax"
FDA_WL_PAGE_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
FDA_BASE_URL = "https://www.fda.gov"

# Standard headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
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
        logging.info("Initiating handshake with FDA Landing Page...")
        response = session.get(FDA_WL_PAGE_URL, timeout=30)

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

            # Set cookies
            domain = urlparse(FDA_WL_PAGE_URL).netloc
            session.cookies.set("authorization_1", auth_1, domain=domain)
            session.cookies.set("authorization_2", auth_2, domain=domain)

            logging.info("Challenge solved. Authorization cookies set.")
            return session
        
        logging.warning(f"Unexpected response: {response.status_code}")
        return None

    except Exception as e:
        logging.error(f"Error during session initialization: {e}", exc_info=True)
        return None

# --- HELPER: PARSERS ---
def _extract_view_dom_id(session: requests.Session) -> str | None:
    """Fetches the landing page to extract the dynamic Drupal view ID."""
    try:
        # Note: We use the authorized session here
        response = session.get(FDA_WL_PAGE_URL, timeout=30)
        match = re.search(r'js-view-dom-id-([a-zA-Z0-9]+)', response.text)
        if match:
            dom_id = match.group(1)
            logging.info(f"Successfully extracted view_dom_id: {dom_id}")
            return dom_id
    except Exception:
        pass
    logging.warning("Could not extract view_dom_id. API calls may fail.")
    return None

def parse_fda_letters(api_response: dict) -> list:
    """Parses the JSON/HTML mix returned by the FDA API."""
    parsed_data = []
    
    # Handle Drupal structure (can be list of commands or direct data dict)
    raw_rows = []
    if isinstance(api_response, list):
        raw_rows = api_response # Fallback
    elif isinstance(api_response, dict) and 'data' in api_response:
        raw_rows = api_response.get('data', [])

    for row in raw_rows:
        try:
            if len(row) < 5: continue

            # Use html.parser for Cloud Run compatibility (no lxml dependency issues)
            soup_posted = BeautifulSoup(row[0], 'html.parser')
            posted_time_tag = soup_posted.find('time')
            
            # Posted Date
            posted_date = None
            if posted_time_tag and posted_time_tag.has_attr('datetime'):
                posted_date = posted_time_tag['datetime'].split('T')[0]
            else:
                # Fallback to text parsing
                text_date = soup_posted.get_text(strip=True)
                try:
                    posted_date = datetime.strptime(text_date, "%m/%d/%Y").strftime("%Y-%m-%d")
                except: pass

            # Issue Date (Column 1)
            # Note: The original script parsed this, keeping it for consistency
            soup_issue = BeautifulSoup(row[1], 'html.parser')
            issue_time_tag = soup_issue.find('time')
            issue_date = None
            if issue_time_tag and issue_time_tag.has_attr('datetime'):
                issue_date = issue_time_tag['datetime'].split('T')[0]

            # Company Name & URL (Column 2)
            soup_company = BeautifulSoup(row[2], 'html.parser')
            company_link = soup_company.find('a')
            company_name = company_link.get_text(strip=True) if company_link else row[2]
            
            letter_url = None
            if company_link and company_link.has_attr('href'):
                href = company_link['href']
                letter_url = href if href.startswith("http") else f"{FDA_BASE_URL}{href}"

            # Issuing Office (Column 3)
            issuing_office = BeautifulSoup(row[3], 'html.parser').get_text(strip=True)

            # Subject (Column 4)
            subject = BeautifulSoup(row[4], 'html.parser').get_text(strip=True)
            
            record = {
                "posted_date": posted_date,
                "issue_date": issue_date,
                "company_name": company_name,
                "issuing_office": issuing_office,
                "subject": subject,
                "letter_url": letter_url,
            }
            parsed_data.append(record)
        except Exception:
            # Silent skip for malformed rows
            continue
            
    return parsed_data

# --- MAIN FUNCTION ---
def check_for_updates(days_to_check: int = 7):
    """
    Main entrypoint. 
    1. Solves Challenge.
    2. Gets Token.
    3. Fetches API Data.
    4. Parses & Filters.
    """
    logging.info(f"Starting FDA letter update check (Last {days_to_check} days).")
    
    # 1. Initialize Session (with Solver)
    session = _solve_challenge_and_get_session()
    if not session:
        logging.error("FDA check failed: Could not initialize authorized session.")
        return None

    # 2. Get Dynamic ID
    view_dom_id = _extract_view_dom_id(session)
    
    # 3. Prepare API Request
    # We ensure headers match what a browser sends after the initial load
    session.headers.update({
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': FDA_WL_PAGE_URL,
        'Origin': FDA_BASE_URL
    })

    params = {
        'field_change_date_2': '2', # '2' = Last 30 Days (hardcoded filter on server side)
        'length': '100',            # Fetch 100 items (usually sufficient for weekly checks)
        'start': '0',
        'view_display_id': 'warning_letter_solr_block',
        'view_name': 'warning_letter_solr_index',
        'view_path': '/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters',
        '_drupal_ajax': '1',
        '_': int(time.time() * 1000)
    }
    if view_dom_id:
        params['view_dom_id'] = view_dom_id

    # 4. Fetch Data
    try:
        logging.info("Fetching data from FDA AJAX endpoint...")
        response = session.get(FDA_AJAX_URL, params=params, timeout=60)
        response.raise_for_status()
        json_content = response.json()
    except Exception as e:
        logging.error(f"FDA API request failed: {e}")
        return None

    # 5. Parse Data
    all_recent_letters = parse_fda_letters(json_content)
    
    # 6. Filter by requested days (Logic from original script)
    cutoff_date = datetime.now() - timedelta(days=days_to_check)
    filtered_letters = [
        letter for letter in all_recent_letters
        if letter.get("posted_date") and datetime.strptime(letter.get("posted_date"), "%Y-%m-%d").date() >= cutoff_date.date()
    ]

    logging.info(f"FDA check complete. Found {len(filtered_letters)} letters in the last {days_to_check} days.")
    return {"data": filtered_letters, "source_url": FDA_WL_PAGE_URL}

if __name__ == "__main__":
    # CLI Test Block
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    result_package = check_for_updates(days_to_check=7)
    
    if result_package and result_package.get("data"):
        logging.info(f"Test run successful. Found {len(result_package['data'])} records.")
        
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fda_letters_{timestamp}.json"
        
        with open(os.path.join(output_dir, filename), "w") as f:
            json.dump(result_package, f, indent=4)
        logging.info(f"Saved package to {os.path.join(output_dir, filename)}")
        
        # Print sample
        if len(result_package['data']) > 0:
            print(json.dumps(result_package['data'][0], indent=2))
    else:
        logging.error("Test run failed or found no records.")