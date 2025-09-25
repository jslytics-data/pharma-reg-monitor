import os
import logging

from dotenv import load_dotenv

from .sources import cdsco_source, edqm_source, fda_source, fda_dmf_source
from . import notifier

def run_all_checks_and_notify():
    logging.info("Manager: Starting orchestration.")

    try:
        days_to_check = int(os.environ.get("DAYS_TO_CHECK", "3"))
    except (ValueError, TypeError):
        logging.warning("Manager: Invalid DAYS_TO_CHECK value. Defaulting to 7.")
        days_to_check = 7

    recipients_str = os.environ.get("RECIPIENT_EMAILS")
    if not recipients_str:
        logging.error("MANAGER HALTING: RECIPIENT_EMAILS environment variable not set.")
        return False

    recipient_list = [email.strip() for email in recipients_str.split(',') if email.strip()]
    if not recipient_list:
        logging.error("MANAGER HALTING: No valid email addresses found in RECIPIENT_EMAILS.")
        return False

    aggregated_results = {}

    # --- Step 1: EDQM ---
    logging.info("Manager: Checking source [EDQM].")
    edqm_updates = edqm_source.check_for_updates(days_to_check)
    if edqm_updates is None:
        logging.error("MANAGER HALTING: The EDQM source failed.")
        return False
    aggregated_results["edqm"] = edqm_updates
    logging.info(f"Manager: EDQM check successful, found {len(edqm_updates)} items.")

    # --- Step 2: CDSCO ---
    logging.info("Manager: Checking source [CDSCO].")
    cdsco_updates = cdsco_source.check_for_updates(days_to_check)
    if cdsco_updates is None:
        logging.error("MANAGER HALTING: The CDSCO source failed.")
        return False
    aggregated_results["cdsco"] = cdsco_updates
    logging.info(f"Manager: CDSCO check successful, found {len(cdsco_updates)} items.")

    # --- Step 3: FDA Warning Letters ---
    logging.info("Manager: Checking source [FDA Warning Letters].")
    fda_updates = fda_source.check_for_updates(days_to_check)
    if fda_updates is None:
        logging.error("MANAGER HALTING: The FDA Warning Letters source failed.")
        return False
    aggregated_results["fda"] = fda_updates
    logging.info(f"Manager: FDA check successful, found {len(fda_updates)} items.")

    # --- Step 4: FDA DMF Date ---
    logging.info("Manager: Checking source [FDA DMF Date].")
    dmf_date = fda_dmf_source.check_dmf_update_date()
    if dmf_date is None:
        logging.error("MANAGER HALTING: The FDA DMF Date source failed.")
        return False
    aggregated_results["dmf"] = {"update_date": dmf_date}
    logging.info(f"Manager: FDA DMF Date check successful, found date: {dmf_date}.")

    # --- Step 5: Notification ---
    logging.info("Manager: All sources successful. Handing off to Notifier.")
    notification_sent = notifier.send_consolidated_notification(
        aggregated_results=aggregated_results,
        recipient_emails=recipient_list
    )

    if not notification_sent:
        logging.error("MANAGER HALTING: The Notifier failed to send the email.")
        return False

    logging.info("Manager: Orchestration complete.")
    return True

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    load_dotenv()
    
    success = run_all_checks_and_notify()
    
    if success:
        logging.info("Manager test run finished SUCCESSFULLY.")
    else:
        logging.error("Manager test run FAILED. Check logs for the specific point of failure.")