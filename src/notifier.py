import os
import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def _sort_data_by_date(data: list, date_key: str) -> list:
    try:
        return sorted(
            data,
            key=lambda x: datetime.strptime(x.get(date_key, '1900-01-01'), '%Y-%m-%d'),
            reverse=True
        )
    except ValueError:
        return data

def _format_header_section() -> str:
    date_str = datetime.now().strftime("%A, %B %d, %Y")
    return f"""
    <tr>
        <td style="padding: 30px; text-align: center;">
            <p style="font-size: 32px; margin: 0;">🔬</p>
            <h1 style="font-size: 24px; color: #2c3e50; margin: 10px 0 5px 0; font-weight: 400;">Daily Regulatory Intelligence Report</h1>
            <p style="font-size: 14px; color: #7f8c8d; margin: 0;">{date_str}</p>
        </td>
    </tr>
    """

def _format_dmf_section(aggregated_results: Dict) -> str:
    dmf_info = aggregated_results.get("dmf", {})
    dmf_date_str = dmf_info.get("update_date")
    dmf_url = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"

    if not dmf_date_str:
        return ""

    try:
        date_obj = datetime.strptime(dmf_date_str, '%Y-%m-%d')
        days_since_update = (datetime.now() - date_obj).days
        formatted_date = date_obj.strftime('%B %d, %Y')

        if days_since_update <= 5:
            icon = "🔔"
            bg_color = "#fffbeb"
            border_color = "#facc15"
            title = "New FDA DMF List Published"
            text_color = "#b45309"
        else:
            icon = "✅"
            bg_color = "#f8f9fa"
            border_color = "#e0e0e0"
            title = "FDA DMF List Status"
            text_color = "#555555"
        
        return f"""
        <tr>
            <td style="padding: 0 30px 20px 30px;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse; background-color: {bg_color}; border-radius: 8px; border: 1px solid {border_color};">
                    <tr>
                        <td style="padding: 15px 20px; font-size: 24px; vertical-align: middle; width: 40px;">{icon}</td>
                        <td style="padding: 15px 20px; vertical-align: middle;">
                            <h3 style="margin: 0; font-size: 16px; color: {text_color}; font-weight: 500;">{title}</h3>
                            <p style="margin: 4px 0 0 0; font-size: 14px; color: #555555;">
                                Last Updated: <strong>{formatted_date}</strong>
                                <a href="{dmf_url}" target="_blank" style="margin-left: 15px; color: #005a9c; text-decoration: none;">View Page &rarr;</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """
    except (ValueError, TypeError):
        return ""

def _format_summary_section(aggregated_results: Dict) -> str:
    source_info = {'edqm': '🇪🇺 EDQM', 'cdsco': '🇮🇳 CDSCO', 'fda': '🇺🇸 FDA'}
    summary_lines = []
    for source, data in aggregated_results.items():
        if isinstance(data, list) and data:
            count = len(data)
            name = source_info.get(source, source.upper())
            summary_lines.append(f'<span style="font-size: 16px; color: #2c3e50; margin-right: 20px;"><strong>{count}</strong> {name}</span>')
    
    if not summary_lines:
        return ""
        
    return f"""
    <tr>
        <td style="padding: 0 30px 30px 30px;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse; background-color: #ffffff; border-radius: 8px; border: 1px solid #e0e0e0;">
                <tr>
                    <td style="padding: 20px;">
                        <h2 style="font-size: 16px; color: #2c3e50; margin: 0 0 10px 0;">Updates by Source:</h2>
                        {''.join(summary_lines)}
                    </td>
                </tr>
            </table>
        </td>
    </tr>
    """

def _format_edqm_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'issue_date_cep')
    header_html = f"""
    <h2 style="font-size: 20px; color: #005a9c; margin: 0; font-weight: 500;">
        <span style="font-size: 24px; vertical-align: middle;">🇪🇺</span> EDQM Certificates of Suitability
        <span style="display: inline-block; background-color: #005a9c; color: #ffffff; font-size: 12px; font-weight: bold; padding: 4px 10px; border-radius: 12px; margin-left: 10px;">{len(data)} New</span>
    </h2>
    <hr style="border: 0; border-top: 2px solid #005a9c; margin: 15px 0;">
    """
    
    rows_html = ""
    for item in sorted_data:
        try:
            date_obj = datetime.strptime(item.get('issue_date_cep'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d,<br>%Y')
        except (ValueError, TypeError):
            formatted_date = item.get('issue_date_cep', 'N/A').replace('-', '<br>')

        holder = item.get('certificate_holder', 'N/A')
        substance = item.get('substance', 'N/A')
        cert_num = item.get('certificate_number', 'N/A')
        
        rows_html += f"""
        <tr>
            <td style="padding: 15px 10px; vertical-align: top; width: 15%; font-size: 14px; color: #555555; border-bottom: 1px solid #eeeeee;">{formatted_date}</td>
            <td style="padding: 15px 10px; vertical-align: top; width: 40%; font-size: 14px; border-bottom: 1px solid #eeeeee;">
                <a href="https://www.google.com/search?q={quote_plus(holder)}" target="_blank" style="color: #005a9c; text-decoration: none; font-weight: 500;">{holder}</a>
            </td>
            <td style="padding: 15px 10px; vertical-align: top; width: 20%; font-size: 14px; color: #555555; border-bottom: 1px solid #eeeeee;">{substance}</td>
            <td style="padding: 15px 10px; vertical-align: top; width: 25%; font-size: 13px; color: #777777; font-family: monospace; text-align: right; border-bottom: 1px solid #eeeeee;">{cert_num}</td>
        </tr>
        """
        
    return f'<tr><td style="padding: 0 30px 30px 30px;">{header_html}<table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">{rows_html}</table></td></tr>'

def _format_cdsco_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'release_date')
    header_html = f"""
    <h2 style="font-size: 20px; color: #D68910; margin: 0; font-weight: 500;">
        <span style="font-size: 24px; vertical-align: middle;">🇮🇳</span> CDSCO Written Confirmations
        <span style="display: inline-block; background-color: #D68910; color: #ffffff; font-size: 12px; font-weight: bold; padding: 4px 10px; border-radius: 12px; margin-left: 10px;">{len(data)} New</span>
    </h2>
    <hr style="border: 0; border-top: 2px solid #D68910; margin: 15px 0;">
    """
    
    rows_html = ""
    for item in sorted_data:
        try:
            date_obj = datetime.strptime(item.get('release_date'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d,<br>%Y')
        except (ValueError, TypeError):
            formatted_date = item.get('release_date', 'N/A').replace('-', '<br>')

        company = item.get('company_name', 'N/A')
        products = item.get('products', 'N/A')
        if len(products) > 70:
            products = products[:67] + "..."

        rows_html += f"""
        <tr>
            <td style="padding: 15px 10px; vertical-align: top; width: 15%; font-size: 14px; color: #555555; border-bottom: 1px solid #eeeeee;">{formatted_date}</td>
            <td style="padding: 15px 10px; vertical-align: top; width: 40%; font-size: 14px; border-bottom: 1px solid #eeeeee;">
                <a href="https://www.google.com/search?q={quote_plus(company)}" target="_blank" style="color: #005a9c; text-decoration: none; font-weight: 500;">{company}</a>
            </td>
            <td style="padding: 15px 10px; vertical-align: top; font-size: 14px; color: #555555; border-bottom: 1px solid #eeeeee;">{products}</td>
            <td style="padding: 15px 10px; vertical-align: top; width: 15%; text-align: right; border-bottom: 1px solid #eeeeee;">
                <a href="{item.get('download_pdf_link', '#')}" target="_blank" style="font-size: 13px; font-weight: bold; color: #D68910; text-decoration: none;">View PDF</a>
            </td>
        </tr>
        """
        
    return f'<tr><td style="padding: 0 30px 30px 30px;">{header_html}<table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">{rows_html}</table></td></tr>'

def _format_fda_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'posted_date')
    header_html = f"""
    <h2 style="font-size: 20px; color: #c0392b; margin: 0; font-weight: 500;">
        <span style="font-size: 24px; vertical-align: middle;">🇺🇸</span> FDA Warning Letters
        <span style="display: inline-block; background-color: #c0392b; color: #ffffff; font-size: 12px; font-weight: bold; padding: 4px 10px; border-radius: 12px; margin-left: 10px;">{len(data)} New</span>
    </h2>
    <hr style="border: 0; border-top: 2px solid #c0392b; margin: 15px 0;">
    """

    rows_html = ""
    for item in sorted_data:
        try:
            date_obj = datetime.strptime(item.get('posted_date'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d,<br>%Y')
        except (ValueError, TypeError):
            formatted_date = item.get('posted_date', 'N/A').replace('-', '<br>')

        company = item.get('company_name', 'N/A')
        office = item.get('issuing_office', 'N/A')

        rows_html += f"""
        <tr>
            <td style="padding: 15px 10px; vertical-align: top; width: 15%; font-size: 14px; color: #555555; border-bottom: 1px solid #eeeeee;">{formatted_date}</td>
            <td style="padding: 15px 10px; vertical-align: top; width: 45%; font-size: 14px; border-bottom: 1px solid #eeeeee;">
                <a href="{item.get('letter_url', '#')}" target="_blank" style="color: #005a9c; text-decoration: none; font-weight: 500;">{company}</a>
            </td>
            <td style="padding: 15px 10px; vertical-align: top; font-size: 14px; color: #555555; border-bottom: 1px solid #eeeeee;">{office}</td>
        </tr>
        """
        
    return f'<tr><td style="padding: 0 30px 30px 30px;">{header_html}<table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">{rows_html}</table></td></tr>'

def format_consolidated_html(aggregated_results: Dict) -> str:
    body = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PharmaReg Monitor Report</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f4f7; font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td>
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="800" style="border-collapse: collapse; margin: 20px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
    """
    body += _format_header_section()
    body += _format_dmf_section(aggregated_results)
    body += _format_summary_section(aggregated_results)
    
    source_formatters = {"edqm": _format_edqm_section, "cdsco": _format_cdsco_section, "fda": _format_fda_section}
    has_list_content = any(isinstance(data, list) and data for data in aggregated_results.values())
    
    if has_list_content:
        for source, data in aggregated_results.items():
            if isinstance(data, list) and data:
                body += source_formatters[source](data)
    else:
        body += """
        <tr>
            <td style="padding: 10px 30px 40px 30px; text-align: center;">
                <p style="font-size: 16px; color: #7f8c8d; margin: 0;">No new list updates found for any monitored source.</p>
            </td>
        </tr>
        """
        
    body += """
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return body

def send_consolidated_notification(aggregated_results: Dict, recipient_emails: List[str]) -> bool:
    sender_email = os.environ.get("SENDER_EMAIL")
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not all([sender_email, api_key, recipient_emails]):
        logging.error("Missing required email configuration.")
        return False

    found_sources = [source.upper() for source, data in aggregated_results.items() if isinstance(data, list) and data]
    today_str = datetime.now().strftime("%Y-%m-%d")

    if not found_sources:
        subject = f"PharmaReg Report: {today_str} - No List Updates Found"
    else:
        total_updates = sum(len(data) for data in aggregated_results.values() if isinstance(data, list))
        subject = f"PharmaReg: {total_updates} New Updates from {', '.join(found_sources)} ({today_str})"

    html_content = format_consolidated_html(aggregated_results)
    message = Mail(from_email=sender_email, to_emails=recipient_emails, subject=subject, html_content=html_content)

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        logging.info(f"Email sent successfully, status: {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    recipients_str = os.environ.get("RECIPIENT_EMAILS", "")
    if not recipients_str:
        logging.error("RECIENT_EMAILS not configured.")
    else:
        recipient_list = [e.strip() for e in recipients_str.split(',') if e.strip()]
        
        recent_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        test_data_recent = {
            "dmf": {"update_date": recent_date},
            "edqm": [{"issue_date_cep": "2025-09-04", "certificate_holder": "MACLEODS PHARMACEUTICALS", "substance": "Nebivolol", "certificate_number": "CEP 2024-172"}],
            "cdsco": [],
            "fda": [{"posted_date": "2025-09-09", "company_name": "Jalisco Fresh Produce, Inc.", "issuing_office": "Imports Division", "letter_url": "#"}]
        }
        logging.info("--- Sending Test Email (Recent DMF Date) ---")
        send_consolidated_notification(test_data_recent, recipient_list)

        old_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        test_data_old = {
            "dmf": {"update_date": old_date},
            "edqm": [], "cdsco": [], "fda": []
        }
        logging.info("\n--- Sending Test Email (Old DMF Date, No Updates) ---")
        send_consolidated_notification(test_data_old, recipient_list)