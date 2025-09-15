import os
import json
import logging
from datetime import datetime

from .sources import cdsco_source, edqm_source, fda_source, fda_dmf_source

def aggregate_all_sources(days_to_check: int) -> dict:
    logging.info(f"Starting data aggregation process for all sources (lookback: {days_to_check} days).")
    
    aggregated_results = {}

    # --- Check for list-based updates (EDQM, CDSCO, FDA WL) ---
    list_based_sources = [
        ("edqm", edqm_source),
        ("cdsco", cdsco_source),
        ("fda", fda_source),
    ]

    for name, module in list_based_sources:
        try:
            logging.info(f"Aggregating data from {name.upper()}.")
            updates = module.check_for_updates(days_to_check=days_to_check)
            aggregated_results[name] = updates
        except Exception as e:
            logging.error(f"Failed to get data from {name.upper()}: {e}", exc_info=True)
            aggregated_results[name] = []

    # --- Check for single-item updates (FDA DMF Date) ---
    try:
        logging.info("Aggregating data from FDA_DMF.")
        dmf_date = fda_dmf_source.check_dmf_update_date()
        aggregated_results["dmf"] = {"update_date": dmf_date}
    except Exception as e:
        logging.error(f"Failed to get data from FDA_DMF: {e}", exc_info=True)
        aggregated_results["dmf"] = {"update_date": None}

    total_items = sum(len(data) for key, data in aggregated_results.items() if isinstance(data, list))
    logging.info(f"Data aggregation complete. Found {total_items} total list items.")
    
    return aggregated_results

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Standard lookback period for testing purposes
    lookback_days = 7
    consolidated_data = aggregate_all_sources(days_to_check=lookback_days)
    
    if consolidated_data:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%d%m_%H%M%S")
        filename = f"consolidated_sources_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(consolidated_data, f, indent=4)
            
        logging.info(f"Successfully saved consolidated data to {filepath}")
    else:
        logging.error("Aggregation process returned no data.")