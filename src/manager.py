import os
import logging

from dotenv import load_dotenv

from . import data_aggregator
from . import notifier

def run_all_checks_and_notify():
    logging.info("Manager: Starting orchestration.")

    try:
        days_to_check = int(os.environ.get("DAYS_TO_CHECK", "7"))
    except (ValueError, TypeError):
        logging.warning("Manager: Invalid DAYS_TO_CHECK value. Defaulting to 7.")
        days_to_check = 7

    recipients_str = os.environ.get("RECIPIENT_EMAILS")
    if not recipients_str:
        logging.error("Manager: Process aborted. RECIPIENT_EMAILS not set.")
        return

    recipient_list = [email.strip() for email in recipients_str.split(',') if email.strip()]
    if not recipient_list:
        logging.error("Manager: Process aborted. No valid emails in RECIPIENT_EMAILS.")
        return

    # Step 1: Call the aggregator to get all consolidated data.
    logging.info("Manager: Handing off to Data Aggregator.")
    consolidated_data = data_aggregator.aggregate_all_sources(days_to_check)
    
    # Step 2: Pass the consolidated data to the notifier to create and send the email.
    logging.info("Manager: Handing off to Notifier.")
    notifier.send_consolidated_notification(
        aggregated_results=consolidated_data,
        recipient_emails=recipient_list
    )

    logging.info("Manager: Orchestration complete.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    load_dotenv()
    run_all_checks_and_notify()