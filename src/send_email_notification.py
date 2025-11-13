import os
import logging
import glob
from typing import List
from dotenv import load_dotenv

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email(subject: str, html_body: str, recipient_emails: List[str]) -> bool:
    if not all([subject, html_body, isinstance(recipient_emails, list), recipient_emails]):
        logging.error("Email sender validation failed: Missing arguments or empty recipient list.")
        return False

    sender_email = os.environ.get("SENDER_EMAIL")
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not all([sender_email, api_key]):
        logging.error("Email sender validation failed: SENDER_EMAIL or SENDGRID_API_KEY is not configured.")
        return False

    message = Mail(
        from_email=sender_email,
        to_emails=recipient_emails,
        subject=subject,
        html_content=html_body
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if 200 <= response.status_code < 300:
            logging.info(f"Email sent successfully to {len(recipient_emails)} recipients, status: {response.status_code}")
            return True
        else:
            logging.error(f"SendGrid returned a non-success status code: {response.status_code}. Body: {response.body}")
            return False
    except Exception as e:
        logging.error(f"An exception occurred while sending email via SendGrid: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    EXPORT_DIR = "exports"

    recipients_str = os.environ.get("RECIPIENT_EMAILS")
    if not recipients_str:
        logging.error("RECIPIENT_EMAILS not configured in .env file for testing.")
    else:
        try:
            list_of_files = glob.glob(os.path.join(EXPORT_DIR, "email_preview_*.html"))
            if not list_of_files:
                raise FileNotFoundError("No email_preview_*.html file found in exports/. Run generate_email_html.py first.")
            
            latest_file = max(list_of_files, key=os.path.getctime)
            with open(latest_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            logging.info(f"Loaded test email body from {os.path.basename(latest_file)}")

            recipient_list = [e.strip() for e in recipients_str.split(',') if e.strip()]
            test_subject = f"PharmaReg Monitor - Test Report"
            
            logging.info("--- Sending Test Email with Real HTML Body ---")
            success = send_email(test_subject, html_content, recipient_list)
            
            if success:
                logging.info("Test email sent successfully.")
            else:
                logging.error("Failed to send test email.")
        except (FileNotFoundError, IndexError, IOError) as e:
            logging.error(f"Test run failed: Could not load test data. {e}")