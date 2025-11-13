import os
import json
import logging
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

FDA_AJAX_URL = "https://www.fda.gov/datatables/views/ajax"
FDA_WL_PAGE_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
FDA_BASE_URL = "https://www.fda.gov"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'X-Requested-With': 'XMLHttpRequest',
    'Connection': 'keep-alive',
    'Referer': FDA_WL_PAGE_URL,
}

def fetch_fda_json():
    max_retries = 3
    backoff_factor = 5
    session = requests.Session()
    session.headers.update(HEADERS)

    params = {
        'field_change_date_2': '1', 'length': '100', 'start': '0',
        'view_display_id': 'warning_letter_solr_block',
        'view_name': 'warning_letter_solr_index',
        'view_path': '/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters',
        '_': int(datetime.now().timestamp() * 1000)
    }

    for attempt in range(max_retries):
        try:
            logging.info(f"Establishing session by visiting main FDA page (Attempt {attempt + 1}/{max_retries})")
            session.get(FDA_WL_PAGE_URL, timeout=60)
            
            logging.info(f"Fetching FDA data via AJAX endpoint")
            response = session.get(FDA_AJAX_URL, params=params, timeout=180)
            response.raise_for_status()
            
            data = response.json()
            logging.info(f"Successfully fetched {len(data.get('data', []))} records from FDA.")
            return data
            
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logging.warning(f"Failed to fetch or decode FDA data on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                sleep_time = backoff_factor * (attempt + 1)
                logging.info(f"Waiting for {sleep_time} seconds before retrying...")
                time.sleep(sleep_time)
            else:
                logging.error(f"All {max_retries} attempts to fetch FDA data failed.", exc_info=True)
                return None
    return None

def parse_fda_letters(api_response: dict):
    if not isinstance(api_response, dict) or 'data' not in api_response or not isinstance(api_response.get('data'), list):
        logging.error("Structural error: FDA API response is malformed or missing the 'data' list.")
        return None

    parsed_data = []
    data_rows = api_response.get('data', [])
    if not data_rows:
        logging.info("FDA response contains zero data rows.")
        return []

    for row in data_rows:
        try:
            soup_posted = BeautifulSoup(row[0], 'lxml')
            posted_time_tag = soup_posted.find('time')
            if not posted_time_tag or not posted_time_tag.has_attr('datetime'):
                logging.warning("Skipping row: could not find valid 'time' tag for posted date.")
                continue

            soup_company = BeautifulSoup(row[2], 'lxml')
            company_link = soup_company.find('a')
            if not company_link or not company_link.has_attr('href'):
                logging.warning("Skipping row: could not find valid company link.")
                continue

            issue_date = None
            soup_issue = BeautifulSoup(row[1], 'lxml')
            issue_time_tag = soup_issue.find('time')
            if issue_time_tag and issue_time_tag.has_attr('datetime'):
                issue_date = issue_time_tag['datetime'].split('T')[0]
            else:
                logging.warning(f"Could not find valid 'time' tag for issue date in '{row[1]}'.")

            record = {
                "posted_date": posted_time_tag['datetime'].split('T')[0],
                "issue_date": issue_date,
                "company_name": company_link.get_text(strip=True),
                "issuing_office": row[3],
                "subject": row[4],
                "letter_url": f"{FDA_BASE_URL}{company_link['href']}",
            }
            parsed_data.append(record)
        except (IndexError, TypeError, AttributeError) as e:
            logging.warning(f"Skipping a malformed FDA row. Error: {e}", exc_info=True)

    logging.info(f"Successfully parsed {len(parsed_data)} FDA letters.")
    return parsed_data

def check_for_updates(days_to_check: int = 7):
    logging.info("Starting FDA letter update check.")

    json_content = fetch_fda_json()
    if json_content is None:
        logging.error("FDA check failed: could not fetch JSON data.")
        return None

    all_recent_letters = parse_fda_letters(json_content)
    if all_recent_letters is None:
        logging.error("FDA check failed: could not parse JSON response.")
        return None

    cutoff_date = datetime.now() - timedelta(days=days_to_check)
    filtered_letters = [
        letter for letter in all_recent_letters
        if datetime.strptime(letter.get("posted_date"), "%Y-%m-%d").date() >= cutoff_date.date()
    ]

    logging.info(f"FDA check complete. Found {len(filtered_letters)} letters in the last {days_to_check} days.")
    return {"data": filtered_letters, "source_url": FDA_WL_PAGE_URL}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    result_package = check_for_updates(days_to_check=7)

    if result_package is not None:
        record_count = len(result_package.get("data", []))
        logging.info(f"Test run successful. Found {record_count} records.")
        logging.info(f"Source URL: {result_package.get('source_url')}")

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