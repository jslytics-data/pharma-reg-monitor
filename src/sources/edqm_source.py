import os
import json
import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://extranet.edqm.eu/4DLink1/4DCGI/Query_CEP"

def fetch_edqm_html(days_ago: int):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_ago)
    
    start_date_str = start_date.strftime("%d/%m/%Y")
    end_date_str = end_date.strftime("%d/%m/%Y")

    params = {
        "vSelectName": "5", "Case_TSE": "none", "vContains": "1",
        "vContainsDate": "4", "vtsubName": "", "vtsubDateBegin": "",
        "vtsubDateBtwBegin": start_date_str, "vtsubDateBtwEnd": end_date_str,
        "SWTP": "1", "OK": "Search"
    }

    try:
        logging.info(f"Fetching EDQM data from {start_date_str} to {end_date_str}")
        response = requests.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        logging.info(f"Successfully fetched {len(response.content)} bytes from EDQM.")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch recent data from EDQM: {e}")
        return None

def parse_edqm_table(html_content: str):
    if not html_content:
        logging.warning("EDQM HTML content is empty, cannot parse.")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    table = soup.find('table', class_='table-scroll')
    if not table:
        logging.warning("Could not find the EDQM results table.")
        return []

    column_headers = [
        "monograph_number", "substance", "type_cep", "certificate_holder",
        "holder_spor_id", "certificate_number", "issue_date_cep",
        "status_cep", "renewal_due", "end_date_cep", "closure_date_of_last_procedure"
    ]
    
    parsed_data = []
    tbody = table.find('tbody')
    if not tbody:
        return []
    
    data_rows = tbody.find_all('tr', class_='header')
    for row in data_rows:
        cells = row.find_all('td')
        if len(cells) == len(column_headers):
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            record = dict(zip(column_headers, cell_texts))

            try:
                date_obj = datetime.strptime(record["issue_date_cep"], "%d/%m/%Y")
                record["issue_date_cep"] = date_obj.strftime("%Y-%m-%d")
            except (ValueError, KeyError):
                logging.warning(f"Could not parse date for EDQM record: {record.get('certificate_number')}")
            
            parsed_data.append(record)
            
    logging.info(f"Successfully parsed {len(parsed_data)} EDQM records.")
    return parsed_data

def check_for_updates(days_to_check: int = 3):
    logging.info("Checking for EDQM certificate updates.")
    html = fetch_edqm_html(days_ago=days_to_check)
    if not html:
        return []
    
    data = parse_edqm_table(html)
    return data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    latest_certificates = check_for_updates(days_to_check=7)
    
    if latest_certificates:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"edqm_certificates_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(latest_certificates, f, indent=4)
            
        logging.info(f"Saved {len(latest_certificates)} records to {filepath}")
    else:
        logging.info("No new EDQM certificates found.")