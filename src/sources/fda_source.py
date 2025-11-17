import os
import json
import logging
import time
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

def _fetch_recent_letters_from_api() -> dict | None:
    params = {
        'field_change_date_2': '2',
        'length': '100',
        'start': '0',
        'view_display_id': 'warning_letter_solr_block',
        'view_name': 'warning_letter_solr_index',
        'view_path': '/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters',
        '_': int(datetime.now().timestamp() * 1000)
    }

    max_retries = 3
    backoff_factor = 5
    for attempt in range(max_retries):
        try:
            logging.info(f"Attempting direct API call with filters (Attempt {attempt + 1}/{max_retries})")
            response = requests.get(FDA_AJAX_URL, headers=HEADERS, params=params, timeout=120, impersonate="chrome110")
            response.raise_for_status()
            json_content = response.json()
            logging.info(f"API call successful. Received {len(json_content.get('data',[]))} records from the last 30 days.")
            return json_content
        except requests.errors.RequestsError as e:
            logging.warning(f"Direct API call failed on attempt {attempt + 1}: {e}")
            if e.response:
                status_code = e.response.status_code
                headers = e.response.headers
                body_snippet = e.response.text[:1000]
                logging.error(f"FDA API Request Failure Details:")
                logging.error(f"  - Status Code: {status_code}")
                logging.error(f"  - Response Headers: {headers}")
                logging.error(f"  - Response Body Snippet: {body_snippet}")
            
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (attempt + 1))
            else:
                logging.error("All attempts for the direct API call failed.", exc_info=False)
                return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON from response. This may indicate an HTML block page was served. Error: {e}")
            return None
    return None

def parse_fda_letters(api_response: dict):
    if not isinstance(api_response, dict) or 'data' not in api_response or not isinstance(api_response.get('data'), list):
        logging.error("Structural error: FDA API response is malformed or missing the 'data' list.")
        return None

    parsed_data = []
    for row in api_response.get('data', []):
        try:
            soup_posted = BeautifulSoup(row[0], 'lxml')
            posted_time_tag = soup_posted.find('time')
            soup_company = BeautifulSoup(row[2], 'lxml')
            company_link = soup_company.find('a')
            soup_issue = BeautifulSoup(row[1], 'lxml')
            issue_time_tag = soup_issue.find('time')

            record = {
                "posted_date": posted_time_tag['datetime'].split('T')[0] if posted_time_tag else None,
                "issue_date": issue_time_tag['datetime'].split('T')[0] if issue_time_tag else None,
                "company_name": company_link.get_text(strip=True) if company_link else row[2],
                "issuing_office": row[3],
                "subject": row[4],
                "letter_url": f"{FDA_BASE_URL}{company_link['href']}" if company_link else None,
            }
            parsed_data.append(record)
        except Exception:
            logging.warning(f"Skipping a malformed FDA row: {row}", exc_info=True)

    logging.info(f"Successfully parsed {len(parsed_data)} FDA letters.")
    return parsed_data

def check_for_updates(days_to_check: int = 7):
    logging.info("Starting FDA letter update check using direct API with filters.")

    json_content = _fetch_recent_letters_from_api()
    if json_content is None:
        logging.error("FDA check failed: could not fetch data from the API.")
        return None

    all_recent_letters = parse_fda_letters(json_content)
    if all_recent_letters is None:
        logging.error("FDA check failed: could not parse the API response.")
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

    if result_package is not None:
        record_count = len(result_package.get("data", []))
        logging.info(f"Test run successful. Found {record_count} records.")
        
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fda_letters_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result_package, f, indent=4)

        logging.info(f"Saved package with {record_count} records to {filepath}")
    else:
        logging.error("Test run failed. The check_for_updates function returned a failure signal (None).")