import os
import json
import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

CDSCO_WC_URL = "https://cdsco.gov.in/opencms/en/International-cell1/"
CDSCO_BASE_URL = "https://cdsco.gov.in"

def fetch_cdsco_html():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"Fetching CDSCO data from {CDSCO_WC_URL}")
        response = requests.get(CDSCO_WC_URL, headers=headers, timeout=60)
        response.raise_for_status()
        logging.info(f"Successfully fetched {len(response.content)} bytes from CDSCO.")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch data from CDSCO: {e}")
        return None

def parse_cdsco_table(html_content: str):
    if not html_content:
        logging.warning("CDSCO HTML content is empty, cannot parse.")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    table = soup.find('table', id='example')
    if not table:
        logging.warning("Could not find the CDSCO results table.")
        return []

    parsed_data = []
    tbody = table.find('tbody')
    if not tbody:
        return []
    
    data_rows = tbody.find_all('tr')
    for row in data_rows:
        cells = row.find_all('td')
        if len(cells) == 7:
            record = {"release_date": cells[4].get_text(strip=True).split(" ")[0]}
            link_tag = cells[5].find('a')
            
            record["s_no"] = cells[0].get_text(strip=True)
            record["wc_number"] = cells[1].get_text(strip=True)
            record["company_name"] = cells[2].get_text(strip=True)
            record["products"] = cells[3].get_text(strip=True)
            record["download_pdf_link"] = f"{CDSCO_BASE_URL}{link_tag['href']}" if link_tag else ""
            record["pdf_size"] = cells[6].get_text(strip=True)
            
            parsed_data.append(record)
            
    logging.info(f"Successfully parsed {len(parsed_data)} CDSCO records.")
    return parsed_data

def check_for_updates(days_to_check: int = 7):
    logging.info("Checking for CDSCO confirmation updates.")
    html = fetch_cdsco_html()
    if not html:
        return []
    
    all_confirmations = parse_cdsco_table(html)
    if not all_confirmations:
        return []

    recent_confirmations = []
    cutoff_date = datetime.now() - timedelta(days=days_to_check)

    for cert in all_confirmations:
        release_date_str = cert.get("release_date")
        if not release_date_str:
            continue
        try:
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
            if release_date.date() >= cutoff_date.date():
                recent_confirmations.append(cert)
        except ValueError:
            logging.warning(f"Could not parse date '{release_date_str}'. Skipping.")
    
    logging.info(f"Found {len(recent_confirmations)} CDSCO confirmations from the last {days_to_check} days.")
    return recent_confirmations

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    latest_confirmations = check_for_updates(days_to_check=7)
    
    if latest_confirmations:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cdsco_confirmations_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(latest_confirmations, f, indent=4)
            
        logging.info(f"Saved {len(latest_confirmations)} records to {filepath}")
    else:
        logging.info("No new CDSCO confirmations found.")