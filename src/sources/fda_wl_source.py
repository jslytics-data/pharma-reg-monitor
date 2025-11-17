import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

FDA_WL_PAGE_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
FDA_BASE_URL = "https://www.fda.gov"

def _parse_fda_html_table(html_content: str) -> Optional[List[Dict[str, Any]]]:
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        table = soup.find('table', id='datatable')
        if not table:
            logging.error("HTML Parser: Could not find the datatable in the HTML content.")
            return None
        
        tbody = table.find('tbody')
        if not tbody: return []

        parsed_data = []
        for row in tbody.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 7: continue

            posted_time_tag = cells[0].find('time')
            issue_time_tag = cells[1].find('time')
            company_link_tag = cells[2].find('a')

            record = {
                "posted_date": posted_time_tag['datetime'].split('T')[0] if posted_time_tag else None,
                "issue_date": issue_time_tag['datetime'].split('T')[0] if issue_time_tag else None,
                "company_name": company_link_tag.get_text(strip=True) if company_link_tag else cells[2].get_text(strip=True),
                "issuing_office": cells[3].get_text(strip=True),
                "subject": cells[4].get_text(strip=True),
                "letter_url": f"{FDA_BASE_URL}{company_link_tag['href']}" if company_link_tag else None,
            }
            parsed_data.append(record)
        
        logging.info(f"HTML Parser: Successfully parsed {len(parsed_data)} records.")
        return parsed_data
    except Exception as e:
        logging.error(f"HTML Parser: An error occurred during parsing: {e}", exc_info=True)
        return None

async def _async_get_filtered_wls(days_to_check: int) -> Optional[Dict[str, Any]]:
    async with async_playwright() as p:
        browser = None
        try:
            logging.info("Browser Scrape: Launching headless browser.")
            browser = await p.chromium.launch()
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            logging.info(f"Browser Scrape: Navigating to page: {FDA_WL_PAGE_URL}")
            await page.goto(FDA_WL_PAGE_URL, timeout=90000, wait_until="domcontentloaded")

            posted_date_filter_selector = 'select[name="field_change_date_2"]'
            show_entries_selector = 'select[name="datatable_length"]'
            await page.wait_for_selector(posted_date_filter_selector, timeout=30000)
            
            # Determine the correct filter value based on days_to_check
            # 1=7d, 2=30d, 3=60d, 4=90d
            filter_value = "1" if days_to_check <= 7 else "2"
            logging.info(f"Browser Scrape: Applying filter for recent data (value: {filter_value}).")
            await page.select_option(posted_date_filter_selector, value=filter_value)
            await page.select_option(show_entries_selector, value="100")
            
            await page.wait_for_selector('#datatable_processing', state='visible', timeout=5000)
            await page.wait_for_selector('#datatable_processing', state='hidden', timeout=30000)
            logging.info("Browser Scrape: Table has reloaded with filtered data.")
            
            html_content = await page.content()
            records = _parse_fda_html_table(html_content)

            if records is None:
                await browser.close()
                return None
            
            await browser.close()
            return {"data": records, "source_url": FDA_WL_PAGE_URL}

        except Exception as e:
            logging.critical(f"Browser Scrape: An unexpected error occurred: {e}", exc_info=True)
            if browser: await browser.close()
            return None

def check_for_updates(days_to_check: int = 7) -> Optional[Dict[str, Any]]:
    logging.info("Starting FDA letter update check using browser automation.")
    try:
        result = asyncio.run(_async_get_filtered_wls(days_to_check))
        if result:
            # Final client-side filter to ensure we only get the exact days requested
            cutoff_date = datetime.now() - timedelta(days=days_to_check)
            filtered_data = [
                r for r in result["data"]
                if r.get("posted_date") and datetime.strptime(r.get("posted_date"), "%Y-%m-%d").date() >= cutoff_date.date()
            ]
            result["data"] = filtered_data
            logging.info(f"Browser Scrape: Complete. Found {len(filtered_data)} letters in the last {days_to_check} days.")
        return result
    except Exception as e:
        logging.error(f"Browser Scrape: Failed to run async task: {e}")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    result_package = check_for_updates(days_to_check=7)
    if result_package:
        logging.info("Test run SUCCESS: Browser automation returned data.")
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"fda_letters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(os.path.join(output_dir, filename), "w") as f:
            json.dump(result_package, f, indent=4)
        logging.info(f"Saved {len(result_package.get('data',[]))} records to {os.path.join(output_dir, filename)}")
    else:
        logging.error("Test run FAILED.")