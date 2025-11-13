import os
import logging
from dotenv import load_dotenv

from .sources import cdsco_source, edqm_source, fda_source, fda_dmf_source
from . import consolidate_results
from . import generate_email_html
from . import send_email_notification

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

    raw_results = {}

    logging.info("Manager: Checking source [EDQM].")
    edqm_updates = edqm_source.check_for_updates(days_to_check)
    if edqm_updates is None:
        logging.error("MANAGER HALTING: The EDQM source failed.")
        return False
    raw_results["edqm"] = edqm_updates
    logging.info("Manager: EDQM check successful.")

    logging.info("Manager: Checking source [CDSCO].")
    cdsco_updates = cdsco_source.check_for_updates(days_to_check)
    if cdsco_updates is None:
        logging.error("MANAGER HALTING: The CDSCO source failed.")
        return False
    raw_results["cdsco"] = cdsco_updates
    logging.info("Manager: CDSCO check successful.")

    logging.info("Manager: Checking source [FDA Warning Letters].")
    fda_updates = fda_source.check_for_updates(days_to_check)
    if fda_updates is None:
        logging.error("MANAGER HALTING: The FDA Warning Letters source failed.")
        return False
    raw_results["fda"] = fda_updates
    logging.info("Manager: FDA check successful.")

    logging.info("Manager: Checking source [FDA DMF Details].")
    dmf_details = fda_dmf_source.check_dmf_details()
    if dmf_details is None:
        logging.error("MANAGER HALTING: The FDA DMF Details source failed.")
        return False
    raw_results["fda_dmf"] = dmf_details
    logging.info("Manager: FDA DMF Details check successful.")

    logging.info("Manager: All sources successful. Handing off to Consolidator.")
    consolidated_report = consolidate_results.consolidate_source_data(raw_results)
    if consolidated_report is None:
        logging.error("MANAGER HALTING: The Consolidator failed.")
        return False

    logging.info("Manager: Consolidation successful. Handing off to HTML Generator.")
    email_package = generate_email_html.generate_html_report(consolidated_report)
    if not email_package:
        logging.error("MANAGER HALTING: The HTML Generator failed.")
        return False

    logging.info("Manager: HTML generation successful. Handing off to Email Sender.")
    notification_sent = send_email_notification.send_email(
        subject=email_package["subject"],
        html_body=email_package["html_body"],
        recipient_emails=recipient_list
    )
    if not notification_sent:
        logging.error("MANAGER HALTING: The Email Sender failed.")
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