import os
import json
import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://extranet.edqm.eu/4DLink1/4DCGI/Query_CEP"
MONOGRAPH_BASE_URL = "https://extranet.edqm.eu/4DLink1/4DCGI/Web_View/mono/"
NO_RESULTS_TEXT = "No record matching your search query was found"

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
        session = requests.Session()
        request = requests.Request('GET', BASE_URL, params=params)
        prepared_request = session.prepare_request(request)
        results_url = prepared_request.url

        logging.info(f"Fetching EDQM data from {results_url}")
        response = session.send(prepared_request, timeout=60)
        response.raise_for_status()

        logging.info(f"Successfully fetched {len(response.content)} bytes from EDQM.")
        return response.text, results_url
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch recent data from EDQM: {e}", exc_info=True)
        return None, None

def parse_edqm_table(html_content: str):
    if not html_content:
        logging.error("Cannot parse empty HTML content.")
        return None

    try:
        soup = BeautifulSoup(html_content, 'lxml')
        table = soup.find('table', class_='table-scroll')

        if not table:
            if NO_RESULTS_TEXT in html_content:
                logging.info("EDQM page confirms zero results for the selected period.")
                return []
            else:
                logging.error("Structural error: EDQM results table is missing and no 'no results' message was found.")
                return None

        column_headers = [
            "monograph_number", "substance", "type_cep", "certificate_holder",
            "holder_spor_id", "certificate_number", "issue_date_cep",
            "status_cep", "renewal_due", "end_date_cep", "closure_date_of_last_procedure"
        ]

        parsed_data = []
        tbody = table.find('tbody')
        if not tbody:
            logging.warning("EDQM table found, but it contains no body/data rows.")
            return []

        data_rows = tbody.find_all('tr', class_='header')
        for row in data_rows:
            cells = row.find_all('td')
            if len(cells) == len(column_headers):
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                record = dict(zip(column_headers, cell_texts))

                if record.get("monograph_number"):
                    record["monograph_url"] = f"{MONOGRAPH_BASE_URL}{record['monograph_number']}"

                try:
                    date_obj = datetime.strptime(record["issue_date_cep"], "%d/%m/%Y")
                    record["issue_date_cep"] = date_obj.strftime("%Y-%m-%d")
                except (ValueError, KeyError):
                    logging.warning(f"Could not parse date for EDQM record: {record.get('certificate_number')}. Skipping date formatting.")

                parsed_data.append(record)

        logging.info(f"Successfully parsed {len(parsed_data)} EDQM records.")
        return parsed_data
    except Exception as e:
        logging.error(f"An unexpected error occurred during EDQM HTML parsing: {e}", exc_info=True)
        return None

def check_for_updates(days_to_check: int = 3):
    logging.info("Starting EDQM update check.")

    html, results_url = fetch_edqm_html(days_ago=days_to_check)
    if html is None:
        logging.error("EDQM check failed: could not fetch HTML.")
        return None

    data = parse_edqm_table(html)
    if data is None:
        logging.error("EDQM check failed: could not parse table.")
        return None

    logging.info(f"EDQM check complete. Found {len(data)} updates.")
    return {"data": data, "source_url": results_url}

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
        filename = f"edqm_certificates_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result_package, f, indent=4)

        logging.info(f"Saved package with {record_count} records to {filepath}")
    else:
        logging.error("Test run failed. The check_for_updates function returned a failure signal (None).")