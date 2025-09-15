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
        <td style="padding: 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px 12px 0 0;">
            <h1 style="font-size: 28px; color: #ffffff; margin: 0; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                PharmaReg Intelligence
            </h1>
            <p style="font-size: 14px; color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-weight: 400;">
                {date_str}
            </p>
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
            icon = "🆕"
            bg_color = "#fef3c7"
            border_color = "#fbbf24"
            status_text = "Recently Updated"
            text_color = "#92400e"
        else:
            icon = "📋"
            bg_color = "#f9fafb"
            border_color = "#e5e7eb"
            status_text = "Current Status"
            text_color = "#6b7280"
        
        return f"""
        <tr>
            <td style="padding: 24px 20px;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                    <tr>
                        <td style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 16px;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td width="32" style="font-size: 20px; padding-right: 12px;">{icon}</td>
                                    <td>
                                        <p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                            FDA DMF LIST • {status_text}
                                        </p>
                                        <p style="margin: 4px 0 0 0; font-size: 14px; color: #374151;">
                                            Last updated: {formatted_date}
                                            <a href="{dmf_url}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 500; margin-left: 8px;">
                                                View →
                                            </a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """
    except (ValueError, TypeError):
        return ""

def _format_summary_section(aggregated_results: Dict) -> str:
    sources = []
    total = 0
    
    source_info = {
        'edqm': {'icon': '🇪🇺', 'name': 'EDQM', 'color': '#3b82f6'},
        'cdsco': {'icon': '🇮🇳', 'name': 'CDSCO', 'color': '#f59e0b'},
        'fda': {'icon': '🇺🇸', 'name': 'FDA', 'color': '#ef4444'}
    }
    
    for source, data in aggregated_results.items():
        if isinstance(data, list) and data:
            count = len(data)
            total += count
            info = source_info.get(source, {'icon': '', 'name': source.upper(), 'color': '#6b7280'})
            sources.append(f"""
                <td style="text-align: center; padding: 0 8px;">
                    <div style="font-size: 24px; margin-bottom: 4px;">{info['icon']}</div>
                    <div style="font-size: 28px; font-weight: 700; color: {info['color']}; margin-bottom: 2px;">{count}</div>
                    <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">{info['name']}</div>
                </td>
            """)
    
    if not sources:
        return """
        <tr>
            <td style="padding: 24px 20px;">
                <div style="background-color: #f9fafb; border-radius: 12px; padding: 32px; text-align: center;">
                    <p style="font-size: 16px; color: #6b7280; margin: 0;">No new updates today</p>
                </div>
            </td>
        </tr>
        """
        
    return f"""
    <tr>
        <td style="padding: 0 20px 24px 20px;">
            <div style="background-color: #fafafa; border-radius: 12px; padding: 24px;">
                <p style="font-size: 14px; color: #6b7280; margin: 0 0 16px 0; text-align: center; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">
                    Today's Updates
                </p>
                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        {''.join(sources)}
                    </tr>
                </table>
            </div>
        </td>
    </tr>
    """

def _format_edqm_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'issue_date_cep')
    
    rows_html = ""
    for i, item in enumerate(sorted_data):
        try:
            date_obj = datetime.strptime(item.get('issue_date_cep'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d')
        except (ValueError, TypeError):
            formatted_date = 'N/A'

        holder = item.get('certificate_holder', 'N/A')
        substance = item.get('substance', 'N/A')
        cert_num = item.get('certificate_number', 'N/A')
        
        bg_color = "#ffffff" if i % 2 == 0 else "#fafafa"
        
        rows_html += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 12px 16px; font-size: 13px; color: #6b7280; white-space: nowrap;">
                {formatted_date}
            </td>
            <td style="padding: 12px 16px; font-size: 14px;">
                <a href="https://www.google.com/search?q={quote_plus(holder)}" target="_blank" style="color: #374151; text-decoration: none; font-weight: 500;">
                    {holder[:40]}{'...' if len(holder) > 40 else ''}
                </a>
            </td>
            <td style="padding: 12px 16px; font-size: 13px; color: #6b7280;">
                {substance[:25]}{'...' if len(substance) > 25 else ''}
            </td>
            <td style="padding: 12px 16px; font-size: 11px; color: #9ca3af; font-family: 'Courier New', monospace; text-align: right;">
                {cert_num[:15]}{'...' if len(cert_num) > 15 else ''}
            </td>
        </tr>
        """
        
    header_html = f"""
    <div style="padding: 20px 20px 0 20px;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td>
                    <h2 style="font-size: 18px; color: #1f2937; margin: 0; font-weight: 600;">
                        🇪🇺 EDQM Certificates
                    </h2>
                </td>
                <td style="text-align: right;">
                    <span style="background-color: #3b82f6; color: #ffffff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 999px;">
                        {len(data)} NEW
                    </span>
                </td>
            </tr>
        </table>
    </div>
    """
    
    return f"""
    <tr>
        <td style="padding-bottom: 24px;">
            {header_html}
            <div style="margin: 16px 20px 0 20px; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f9fafb; border-bottom: 1px solid #e5e7eb;">
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Date</th>
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Holder</th>
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Substance</th>
                            <th style="padding: 10px 16px; text-align: right; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Cert #</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </td>
    </tr>
    """

def _format_cdsco_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'release_date')
    
    rows_html = ""
    for i, item in enumerate(sorted_data):
        try:
            date_obj = datetime.strptime(item.get('release_date'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d')
        except (ValueError, TypeError):
            formatted_date = 'N/A'

        company = item.get('company_name', 'N/A')
        products = item.get('products', 'N/A')
        if len(products) > 40:
            products = products[:37] + "..."

        bg_color = "#ffffff" if i % 2 == 0 else "#fafafa"

        rows_html += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 12px 16px; font-size: 13px; color: #6b7280; white-space: nowrap;">
                {formatted_date}
            </td>
            <td style="padding: 12px 16px; font-size: 14px;">
                <a href="https://www.google.com/search?q={quote_plus(company)}" target="_blank" style="color: #374151; text-decoration: none; font-weight: 500;">
                    {company[:35]}{'...' if len(company) > 35 else ''}
                </a>
            </td>
            <td style="padding: 12px 16px; font-size: 13px; color: #6b7280;">
                {products}
            </td>
            <td style="padding: 12px 16px; text-align: right;">
                <a href="{item.get('download_pdf_link', '#')}" target="_blank" style="color: #f59e0b; text-decoration: none; font-size: 12px; font-weight: 600;">
                    PDF →
                </a>
            </td>
        </tr>
        """
        
    header_html = f"""
    <div style="padding: 20px 20px 0 20px;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td>
                    <h2 style="font-size: 18px; color: #1f2937; margin: 0; font-weight: 600;">
                        🇮🇳 CDSCO Written Confirmations
                    </h2>
                </td>
                <td style="text-align: right;">
                    <span style="background-color: #f59e0b; color: #ffffff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 999px;">
                        {len(data)} NEW
                    </span>
                </td>
            </tr>
        </table>
    </div>
    """
    
    return f"""
    <tr>
        <td style="padding-bottom: 24px;">
            {header_html}
            <div style="margin: 16px 20px 0 20px; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f9fafb; border-bottom: 1px solid #e5e7eb;">
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Date</th>
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Company</th>
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Products</th>
                            <th style="padding: 10px 16px; text-align: right; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Doc</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </td>
    </tr>
    """

def _format_fda_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'posted_date')
    
    rows_html = ""
    for i, item in enumerate(sorted_data):
        try:
            date_obj = datetime.strptime(item.get('posted_date'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d')
        except (ValueError, TypeError):
            formatted_date = 'N/A'

        company = item.get('company_name', 'N/A')
        office = item.get('issuing_office', 'N/A')
        if len(office) > 30:
            office = office[:27] + "..."

        bg_color = "#ffffff" if i % 2 == 0 else "#fafafa"

        rows_html += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 12px 16px; font-size: 13px; color: #6b7280; white-space: nowrap;">
                {formatted_date}
            </td>
            <td style="padding: 12px 16px; font-size: 14px;">
                <a href="{item.get('letter_url', '#')}" target="_blank" style="color: #374151; text-decoration: none; font-weight: 500;">
                    {company[:40]}{'...' if len(company) > 40 else ''}
                </a>
            </td>
            <td style="padding: 12px 16px; font-size: 13px; color: #6b7280;">
                {office}
            </td>
        </tr>
        """
        
    header_html = f"""
    <div style="padding: 20px 20px 0 20px;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td>
                    <h2 style="font-size: 18px; color: #1f2937; margin: 0; font-weight: 600;">
                        🇺🇸 FDA Warning Letters
                    </h2>
                </td>
                <td style="text-align: right;">
                    <span style="background-color: #ef4444; color: #ffffff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 999px;">
                        {len(data)} NEW
                    </span>
                </td>
            </tr>
        </table>
    </div>
    """
    
    return f"""
    <tr>
        <td style="padding-bottom: 24px;">
            {header_html}
            <div style="margin: 16px 20px 0 20px; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f9fafb; border-bottom: 1px solid #e5e7eb;">
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Date</th>
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Company</th>
                            <th style="padding: 10px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Office</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </td>
    </tr>
    """

def format_consolidated_html(aggregated_results: Dict) -> str:
    body = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>PharmaReg Intelligence Report</title>
        <!--[if mso]>
        <noscript>
            <xml>
                <o:OfficeDocumentSettings>
                    <o:AllowPNG/>
                    <o:PixelsPerInch>96</o:PixelsPerInch>
                </o:OfficeDocumentSettings>
            </xml>
        </noscript>
        <![endif]-->
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f3f4f6;">
            <tr>
                <td align="center" style="padding: 40px 0;">
                    <!--[if (gte mso 9)|(IE)]>
                    <table align="center" border="0" cellspacing="0" cellpadding="0" width="600">
                    <tr>
                    <td align="center" valign="top" width="600">
                    <![endif]-->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06); overflow: hidden;">
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
        
        # Add footer
        body += """
        <tr>
            <td style="padding: 24px; background-color: #f9fafb; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 12px; color: #9ca3af; margin: 0; text-align: center;">
                    © 2025 PharmaReg Intelligence • Automated Regulatory Monitoring
                </p>
            </td>
        </tr>
        """
        
    body += """
                    </table>
                    <!--[if (gte mso 9)|(IE)]>
                    </td>
                    </tr>
                    </table>
                    <![endif]-->
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
    today_str = datetime.now().strftime("%B %d, %Y")

    if not found_sources:
        subject = f"PharmaReg Intelligence | {today_str} - No Updates"
    else:
        total_updates = sum(len(data) for data in aggregated_results.values() if isinstance(data, list))
        subject = f"PharmaReg Intelligence | {total_updates} New Updates - {today_str}"

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
        logging.error("RECIPIENT_EMAILS not configured.")
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