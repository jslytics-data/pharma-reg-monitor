import os
import logging

from dotenv import load_dotenv

from . import notifier
from .sources import cdsco_source, edqm_source, fda_source, fda_dmf_source

def run_all_checks_and_notify():
    logging.info("Starting PharmaReg unified check process.")

    try:
        days_to_check = int(os.environ.get("DAYS_TO_CHECK", "7"))
    except (ValueError, TypeError):
        logging.warning("Invalid DAYS_TO_CHECK value. Defaulting to 7 days.")
        days_to_check = 7

    recipients_str = os.environ.get("RECIPIENT_EMAILS")
    if not recipients_str:
        logging.error("Process aborted: RECIPIENT_EMAILS not set.")
        return

    recipient_list = [email.strip() for email in recipients_str.split(',') if email.strip()]
    if not recipient_list:
        logging.error("Process aborted: No valid emails in RECIPIENT_EMAILS.")
        return

    aggregated_results = {}
    
    # --- Check for list-based updates (EDQM, CDSCO, FDA WL) ---
    sources_to_check = [
        ("edqm", edqm_source),
        ("cdsco", cdsco_source),
        ("fda", fda_source),
    ]

    for name, module in sources_to_check:
        try:
            logging.info(f"Checking for updates from {name.upper()}.")
            updates = module.check_for_updates(days_to_check=days_to_check)
            aggregated_results[name] = updates
        except Exception as e:
            logging.error(f"Failed to get updates from {name.upper()}: {e}", exc_info=True)
            aggregated_results[name] = []

    # --- Check for single-item updates (FDA DMF Date) ---
    try:
        dmf_date = fda_dmf_source.check_dmf_update_date()
        aggregated_results["dmf"] = {"update_date": dmf_date}
        if dmf_date:
            logging.info(f"Successfully retrieved FDA DMF update date: {dmf_date}")
    except Exception as e:
        logging.error(f"Failed to get FDA DMF update date: {e}", exc_info=True)
        aggregated_results["dmf"] = {"update_date": None}

    total_updates = sum(len(data) for key, data in aggregated_results.items() if isinstance(data, list))
    logging.info(f"Completed all checks. Found a total of {total_updates} list updates.")

    notifier.send_consolidated_notification(
        aggregated_results=aggregated_results,
        recipient_emails=recipient_list
    )

    logging.info("PharmaReg unified check and notification process finished.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    load_dotenv()
    run_all_checks_and_notify()