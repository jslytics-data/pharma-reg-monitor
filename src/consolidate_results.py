import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import glob

def consolidate_source_data(raw_source_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_source_results, dict):
        logging.error("Consolidator: Input must be a dictionary.")
        return None

    logging.info("Consolidator: Starting consolidation of raw source data.")
    consolidated_report = {}
    total_updates = 0

    for source_name, source_package in raw_source_results.items():
        if source_package is None:
            logging.warning(f"Consolidator: Received a null package for source '{source_name}'. Skipping.")
            continue

        if isinstance(source_package.get("data"), list):
            updates = source_package.get("data", [])
            update_count = len(updates)
            consolidated_report[source_name] = {
                "updates": updates,
                "source_url": source_package.get("source_url", ""),
                "update_count": update_count,
            }
            total_updates += update_count
            logging.info(f"Consolidator: Processed '{source_name}' with {update_count} updates.")

        elif isinstance(source_package, dict) and "update_date" in source_package:
             consolidated_report[source_name] = source_package
             logging.info(f"Consolidator: Processed '{source_name}' with date {source_package.get('update_date')}.")

        else:
            logging.warning(f"Consolidator: Unrecognized package structure for source '{source_name}'. Skipping.")

    consolidated_report["total_updates"] = total_updates
    logging.info(f"Consolidator: Consolidation complete. Total updates across all sources: {total_updates}.")

    return consolidated_report

def _find_latest_export_file(directory: str, prefix: str) -> Optional[str]:
    try:
        search_path = os.path.join(directory, f"{prefix}*.json")
        list_of_files = glob.glob(search_path)
        if not list_of_files:
            return None
        latest_file = max(list_of_files, key=os.path.getctime)
        return latest_file
    except Exception as e:
        logging.error(f"Error finding latest file for prefix {prefix}: {e}")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    EXPORT_DIR = "exports"

    if not os.path.isdir(EXPORT_DIR):
        logging.error(f"Test run failed: The '{EXPORT_DIR}' directory does not exist. Please run the source scripts first.")
    else:
        raw_results_from_files = {}
        source_map = {
            "edqm": "edqm_certificates",
            "cdsco": "cdsco_confirmations",
            "fda": "fda_letters",
            "fda_dmf": "fda_dmf_details"
        }

        for key, prefix in source_map.items():
            latest_file = _find_latest_export_file(EXPORT_DIR, prefix)
            if not latest_file:
                logging.warning(f"No export file found for source '{key}'. Skipping.")
                continue

            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data_package = json.load(f)
                raw_results_from_files[key] = data_package
                logging.info(f"Successfully loaded '{key}' package from {os.path.basename(latest_file)}")
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Failed to load or parse {latest_file}: {e}")

        if not raw_results_from_files:
            logging.error("Could not load any data from export files. Halting test run.")
        else:
            final_report_data = consolidate_source_data(raw_results_from_files)

            if final_report_data:
                logging.info("Test run SUCCESS: Consolidation of file data was successful.")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"consolidated_report_{timestamp}.json"
                filepath = os.path.join(EXPORT_DIR, filename)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(final_report_data, f, indent=4)
                logging.info(f"Saved consolidated report to {filepath}")
            else:
                logging.error("Test run FAILED: Consolidation returned a failure signal (None).")