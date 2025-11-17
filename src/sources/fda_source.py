import os
import json
import logging
import time
import re
from datetime import datetime, timedelta

from curl_cffi import requests
from bs4 import BeautifulSoup

FDA_AJAX_URL = "https://www.fda.gov/datatables/views/ajax"
FDA_WL_PAGE_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
FDA_BASE_URL = "https://www.fda.gov"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': FDA_WL_PAGE_URL,
    'X-Requested-With': 'XMLHttpRequest',
}

def _get_view_dom_id(session: requests.Session) -> str | None:
    try:
        logging.info("Fetching main page to acquire session token (view_dom_id)...")
        response = session.get(FDA_WL_PAGE_URL, headers=HEADERS, timeout=60, impersonate="chrome110")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        view_div = soup.find('div', class_=re.compile(r"js-view-dom-id-"))
        if not view_div:
            logging.error("Could not find the main view div to extract the view_dom_id.")
            return None
        
        class_list = view_div.get('class', [])
        dom_id_class = next((cls for cls in class_list if cls.startswith('js-view-dom-id-')), None)

        if dom_id_class:
            view_dom_id = dom_id_class.replace('js-view-dom-id-', '')
            logging.info(f"Successfully acquired session token: {view_dom_id}")
            return view_dom_id
            
        logging.error("Could not extract view_dom_id from the page HTML.")
        return None
    except requests.errors.RequestsError as e:
        logging.error(f"Failed to fetch the main page to get session token: {e}")
        return None

def _fetch_recent_letters_from_api(session: requests.Session, view_dom_id: str) -> dict | None:
    params = {
        'field_change_date_2': '2',
        'length': '100',
        'view_display_id': 'warning_letter_solr_block',
        'view_name': 'warning_letter_solr_index',
        'view_path': '/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters',
        '_drupal_ajax': '1',
        'view_dom_id': view_dom_id,
        '_': int(datetime.now().timestamp() * 1000)
    }
    
    try:
        logging.info(f"Attempting direct API call with session token...")
        response = session.get(FDA_AJAX_URL, headers=HEADERS, params=params, timeout=120, impersonate="chrome110")
        response.raise_for_status()
        json_data = response.json()
        logging.info(f"API call successful. Received {len(json_data.get('data',[]))} records.")
        return json_data
    except (requests.errors.RequestsError, json.JSONDecodeError) as e:
        logging.error(f"Direct API call failed: {e}", exc_info=True)
        return None

def parse_fda_letters(api_response: dict):
    if not isinstance(api_response, dict) or 'data' not in api_response or not isinstance(api_response.get('data'), list):
        logging.error("Structural error: API response is malformed or missing the 'data' list.")
        return None

    parsed_data = []
    for row in api_response.get('data', []):
        try:
            soup_posted = BeautifulSoup(row[0], 'lxml')
            posted_time_tag = soup_posted.find('time')
            soup_issue = BeautifulSoup(row[1], 'lxml')
            issue_time_tag = soup_issue.find('time')
            soup_company = BeautifulSoup(row[2], 'lxml')
            company_link = soup_company.find('a')
            
            record = {
                "posted_date": posted_time_tag['datetime'].split('T')[0] if posted_time_tag else None,
                "issue_date": issue_time_tag['datetime'].split('T')[0] if issue_time_tag else None,
                "company_name": company_link.get_text(strip=True) if company_link else row[2],
                "issuing_office": BeautifulSoup(row[3], 'lxml').get_text(strip=True),
                "subject": BeautifulSoup(row[4], 'lxml').get_text(strip=True),
                "letter_url": f"{FDA_BASE_URL}{company_link['href']}" if company_link else None,
            }
            parsed_data.append(record)
        except Exception:
            logging.warning(f"Skipping a malformed FDA row.", exc_info=True)
    logging.info(f"Successfully parsed {len(parsed_data)} FDA letters.")
    return parsed_data

def check_for_updates(days_to_check: int = 7):
    logging.info("Starting FDA letter update check using two-step API approach.")
    
    with requests.Session() as session:
        view_dom_id = _get_view_dom_id(session)
        if not view_dom_id:
            logging.error("FDA check failed: could not acquire session token.")
            return None

        json_content = _fetch_recent_letters_from_api(session, view_dom_id)
    
    if json_content is None:
        return None

    all_recent_letters = parse_fda_letters(json_content)
    if all_recent_letters is None:
        return None

    cutoff_date = datetime.now() - timedelta(days=days_to_check)
    filtered_letters = [
        letter for letter in all_recent_letters
        if letter.get("posted_date") and datetime.strptime(letter.get("posted_date"), "%Y-%m-%d").date() >= cutoff_date.date()
    ]

    logging.info(f"FDA check complete. Found {len(filtered_letters)} letters in the last {days_to_check} days.")
    return {"data": filtered_letters, "source_url": FDA_WL_PAGE_URL}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    result_package = check_for_updates(days_to_check=7)
    if result_package:
        logging.info(f"Test run successful. Found {len(result_package['data'])} records.")
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fda_letters_{timestamp}.json"
        with open(os.path.join(output_dir, filename), "w") as f:
            json.dump(result_package, f, indent=4)
        logging.info(f"Saved package to {os.path.join(output_dir, filename)}")
    else:
        logging.error("Test run failed.")