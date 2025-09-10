import os
import json
import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

FDA_AJAX_URL = "https://www.fda.gov/datatables/views/ajax"
FDA_WL_PAGE_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
FDA_BASE_URL = "https://www.fda.gov"

def fetch_fda_json():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Referer': FDA_WL_PAGE_URL,
    }
    params = {
        'field_change_date_2': '1', 'length': '100', 'start': '0',
        'view_display_id': 'warning_letter_solr_block',
        'view_name': 'warning_letter_solr_index',
        'view_path': '/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters',
        '_': int(datetime.now().timestamp() * 1000)
    }
    try:
        logging.info("Fetching last 7 days of FDA data via AJAX endpoint.")
        response = requests.get(FDA_AJAX_URL, headers=headers, params=params, timeout=180)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Successfully fetched {len(data.get('data', []))} records from FDA.")
        return data
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        logging.error(f"Failed to fetch or decode FDA data: {e}")
        return None

def parse_fda_letters(api_response: dict):
    if not api_response or 'data' not in api_response:
        logging.warning("FDA response is empty or missing 'data' key.")
        return []

    data_rows = api_response.get('data', [])
    parsed_data = []

    for row in data_rows:
        try:
            soup_posted = BeautifulSoup(row[0], 'lxml')
            soup_company = BeautifulSoup(row[2], 'lxml')
            company_link = soup_company.find('a')
            
            record = {
                "posted_date": soup_posted.find('time')['datetime'].split('T')[0],
                "company_name": company_link.get_text(strip=True),
                "issuing_office": row[3],
                "subject": row[4],
                "letter_url": f"{FDA_BASE_URL}{company_link['href']}",
            }
            parsed_data.append(record)
        except (IndexError, TypeError, AttributeError) as e:
            logging.warning(f"Skipping a malformed FDA row. Error: {e}")
            
    logging.info(f"Successfully parsed {len(parsed_data)} FDA letters.")
    return parsed_data

def check_for_updates(days_to_check: int = 7):
    logging.info("Checking for FDA letter updates.")
    days_to_check = min(days_to_check, 7)
    
    json_content = fetch_fda_json()
    if not json_content:
        return []
    
    all_recent_letters = parse_fda_letters(json_content)
    if not all_recent_letters:
        return []
        
    cutoff_date = datetime.now() - timedelta(days=days_to_check)
    filtered_letters = [
        letter for letter in all_recent_letters
        if datetime.strptime(letter.get("posted_date"), "%Y-%m-%d").date() >= cutoff_date.date()
    ]
    
    logging.info(f"Found {len(filtered_letters)} FDA letters from the last {days_to_check} days.")
    return filtered_letters

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    latest_letters = check_for_updates(days_to_check=7)
    
    if latest_letters:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fda_letters_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(latest_letters, f, indent=4)
            
        logging.info(f"Saved {len(latest_letters)} records to {filepath}")
    else:
        logging.info("No new FDA letters found.")