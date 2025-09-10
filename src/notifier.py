import os
import logging
from datetime import datetime
from urllib.parse import quote_plus
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

COLORS = {
    'edqm': '#005a9c', 'cdsco': '#ff9933', 'fda': '#c0392b',
    'primary': '#2c3e50', 'secondary': '#7f8c8d',
}

def _sort_data_by_date(data: list, date_key: str, date_format: str) -> list:
    try:
        return sorted(
            data,
            key=lambda x: datetime.strptime(x.get(date_key, '1900-01-01'), date_format),
            reverse=True
        )
    except ValueError as e:
        logging.warning(f"Could not sort data using key '{date_key}': {e}")
        return data

def _get_summary_stats(aggregated_results: Dict) -> Dict:
    total_updates = sum(len(data) for data in aggregated_results.values())
    sources_with_updates = sum(1 for data in aggregated_results.values() if data)
    stats = {
        'total': total_updates,
        'sources': sources_with_updates,
        'by_source': {source: len(data) for source, data in aggregated_results.items()}
    }
    return stats

def _count_unique_companies(aggregated_results: Dict) -> int:
    companies = set()
    key_map = {'edqm': 'certificate_holder', 'cdsco': 'company_name', 'fda': 'company_name'}
    for source, data in aggregated_results.items():
        for item in data:
            company = item.get(key_map.get(source), '')
            if company:
                companies.add(company.strip().lower())
    return len(companies)

def _format_summary_section(aggregated_results: Dict) -> str:
    stats = _get_summary_stats(aggregated_results)
    html = """
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; padding: 25px; margin-bottom: 30px; color: white;">
        <h2 style="margin: 0 0 20px 0; font-size: 24px; font-weight: 300;">📊 Today's Regulatory Updates Summary</h2>
        <div style="display: table; width: 100%;">
            <div style="display: table-row;">
    """
    stat_cards = [
        ('🔔', 'Total Updates', stats['total']),
        ('📋', 'Active Sources', stats['sources']),
        ('🏢', 'Companies Affected', _count_unique_companies(aggregated_results))
    ]
    for icon, label, value in stat_cards:
        html += f"""
            <div style="display: table-cell; text-align: center; padding: 0 15px;">
                <div style="font-size: 28px; margin-bottom: 5px;">{icon}</div>
                <div style="font-size: 32px; font-weight: bold;">{value}</div>
                <div style="font-size: 14px; opacity: 0.9; margin-top: 5px;">{label}</div>
            </div>
        """
    html += """</div></div></div>"""
    if stats['total'] > 0:
        html += """
        <div style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 30px;">
            <h3 style="margin: 0 0 15px 0; color: #2c3e50; font-size: 16px;">Updates by Source:</h3>
            <div style="display: table; width: 100%;">
        """
        source_info = {'edqm': ('🇪🇺', 'EDQM'), 'cdsco': ('🇮🇳', 'CDSCO'), 'fda': ('🇺🇸', 'FDA')}
        for source, count in stats['by_source'].items():
            if count > 0:
                icon, name = source_info.get(source, ('📄', source.upper()))
                color = COLORS.get(source, '#666')
                html += f"""
                <div style="display: inline-block; margin-right: 20px; margin-bottom: 10px;">
                    <span style="font-size: 20px; vertical-align: middle;">{icon}</span>
                    <span style="color: {color}; font-weight: bold; font-size: 18px; margin: 0 8px;">{count}</span>
                    <span style="color: #666; font-size: 14px;">{name}</span>
                </div>
                """
        html += """</div></div>"""
    return html

def _format_edqm_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'issue_date_cep', '%Y-%m-%d')
    html = f"""
    <div style="margin-bottom: 40px;">
        <div style="display: flex; align-items: center; border-bottom: 2px solid {COLORS['edqm']}; padding-bottom: 10px; margin-bottom: 20px;">
            <span style="font-size: 28px; margin-right: 12px;">🇪🇺</span>
            <h2 style="color: {COLORS['edqm']}; margin: 0; font-size: 22px;">EDQM Certificates of Suitability
                <span style="background: {COLORS['edqm']}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 14px; margin-left: 10px;">{len(data)} New</span>
            </h2>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
            <thead>
                <tr style="background: linear-gradient(135deg, #005a9c 0%, #0074d9 100%); color: white;">
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Issue Date</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Certificate Holder</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Substance</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Certificate №</th>
                </tr>
            </thead>
            <tbody>
    """
    for i, item in enumerate(sorted_data):
        row_bg = "#ffffff" if i % 2 == 0 else "#f8f9fa"
        substance = item.get('substance', 'N/A')
        holder = item.get('certificate_holder', 'N/A')
        try:
            date_obj = datetime.strptime(item.get('issue_date_cep'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d, %Y')
        except (ValueError, TypeError):
            formatted_date = item.get('issue_date_cep', 'N/A')
        html += f"""
        <tr style="background-color: {row_bg};">
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef;">{formatted_date}</td>
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef;">
                <a href="https://www.google.com/search?q={quote_plus(holder)}" target="_blank" style="color: {COLORS['edqm']}; text-decoration: none;">{holder}</a>
            </td>
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef;">{substance}</td>
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef; font-family: monospace;">{item.get('certificate_number', 'N/A')}</td>
        </tr>
        """
    html += """</tbody></table></div>"""
    return html

def _format_cdsco_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'release_date', '%Y-%m-%d')
    html = f"""
    <div style="margin-bottom: 40px;">
        <div style="display: flex; align-items: center; border-bottom: 2px solid {COLORS['cdsco']}; padding-bottom: 10px; margin-bottom: 20px;">
            <span style="font-size: 28px; margin-right: 12px;">🇮🇳</span>
            <h2 style="color: {COLORS['cdsco']}; margin: 0; font-size: 22px;">CDSCO Written Confirmations
                <span style="background: {COLORS['cdsco']}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 14px; margin-left: 10px;">{len(data)} New</span>
            </h2>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
            <thead>
                <tr style="background: linear-gradient(135deg, #ff9933 0%, #ffb366 100%); color: white;">
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Release Date</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Company</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Products</th>
                    <th style="padding: 14px; text-align: center; font-weight: 500;">Document</th>
                </tr>
            </thead>
            <tbody>
    """
    for i, item in enumerate(sorted_data):
        row_bg = "#ffffff" if i % 2 == 0 else "#f8f9fa"
        company = item.get('company_name', 'N/A')
        products = item.get('products', 'N/A')
        if len(products) > 60:
            products = products[:57] + "..."
        try:
            date_obj = datetime.strptime(item.get('release_date'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d, %Y')
        except (ValueError, TypeError):
            formatted_date = item.get('release_date', 'N/A')
        html += f"""
        <tr style="background-color: {row_bg};">
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef;">{formatted_date}</td>
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef;">
                <a href="https://www.google.com/search?q={quote_plus(company)}" target="_blank" style="color: {COLORS['edqm']}; text-decoration: none;">{company}</a>
            </td>
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef;">{products}</td>
            <td style="padding: 14px; border-bottom: 1px solid #e9ecef; text-align: center;">
                <a href="{item.get('download_pdf_link', '#')}" target="_blank" style="display: inline-block; background: {COLORS['cdsco']}; color: white; padding: 6px 16px; border-radius: 4px; text-decoration: none;">📄 PDF</a>
            </td>
        </tr>
        """
    html += """</tbody></table></div>"""
    return html

def _format_fda_section(data: List[Dict]) -> str:
    sorted_data = _sort_data_by_date(data, 'posted_date', '%Y-%m-%d')
    html = f"""
    <div style="margin-bottom: 40px;">
        <div style="display: flex; align-items: center; border-bottom: 2px solid {COLORS['fda']}; padding-bottom: 10px; margin-bottom: 20px;">
            <span style="font-size: 28px; margin-right: 12px;">🇺🇸</span>
            <h2 style="color: {COLORS['fda']}; margin: 0; font-size: 22px;">FDA Warning Letters
                <span style="background: {COLORS['fda']}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 14px; margin-left: 10px;">⚠️ {len(data)} New</span>
            </h2>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
            <thead>
                <tr style="background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%); color: white;">
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Posted Date</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Company</th>
                    <th style="padding: 14px; text-align: left; font-weight: 500;">Issuing Office</th>
                    <th style="padding: 14px; text-align: center; font-weight: 500;">Action</th>
                </tr>
            </thead>
            <tbody>
    """
    for i, item in enumerate(sorted_data):
        row_bg = "#fff5f5" if i % 2 == 0 else "#fff9f9"
        company = item.get('company_name', 'N/A')
        try:
            date_obj = datetime.strptime(item.get('posted_date'), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d, %Y')
        except (ValueError, TypeError):
            formatted_date = item.get('posted_date', 'N/A')
        html += f"""
        <tr style="background-color: {row_bg};">
            <td style="padding: 14px; border-bottom: 1px solid #ffe0e0;">{formatted_date}</td>
            <td style="padding: 14px; border-bottom: 1px solid #ffe0e0;">
                 <a href="https://www.google.com/search?q={quote_plus(company)}" target="_blank" style="color: {COLORS['edqm']}; text-decoration: none;">{company}</a>
            </td>
            <td style="padding: 14px; border-bottom: 1px solid #ffe0e0;">{item.get('issuing_office', 'N/A')}</td>
            <td style="padding: 14px; border-bottom: 1px solid #ffe0e0; text-align: center;">
                <a href="{item.get('letter_url', '#')}" target="_blank" style="display: inline-block; background: {COLORS['fda']}; color: white; padding: 6px 16px; border-radius: 4px; text-decoration: none;">⚠️ View Letter</a>
            </td>
        </tr>
        """
    html += """</tbody></table></div>"""
    return html

def format_consolidated_html(aggregated_results: Dict) -> str:
    body = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5;">
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 900px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 0 20px rgba(0,0,0,0.1);">
            <div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 32px; font-weight: 300; letter-spacing: 1px;">🔬 PharmaReg Monitor</h1>
                <p style="color: #ecf0f1; margin: 10px 0 0 0; font-size: 16px;">Daily Regulatory Intelligence Report</p>
                <p style="color: #bdc3c7; margin: 5px 0 0 0; font-size: 14px;">""" + datetime.now().strftime("%A, %B %d, %Y") + """</p>
            </div>
            <div style="padding: 30px;">
    """
    body += _format_summary_section(aggregated_results)
    source_formatters = {"edqm": _format_edqm_section, "cdsco": _format_cdsco_section, "fda": _format_fda_section}
    has_content = False
    for source, data in aggregated_results.items():
        if data:
            formatter = source_formatters.get(source)
            if formatter:
                body += formatter(data)
                has_content = True
    if not has_content:
        body += """
        <div style="text-align: center; padding: 60px 20px;">
            <span style="font-size: 48px;">📭</span>
            <h2 style="color: #7f8c8d; margin: 20px 0;">No Updates Today</h2>
            <p style="color: #95a5a6;">All monitored sources are clear. No new updates found.</p>
        </div>
        """
    body += """
            </div>
            <div style="background: #2c3e50; padding: 25px; text-align: center;">
                 <p style="color: #95a5a6; margin: 10px 0 0 0; font-size: 12px;">This is an automated report generated by PharmaReg Monitor.</p>
                 <p style="color: #7f8c8d; margin: 5px 0 0 0; font-size: 11px;">Generated on """ + datetime.now().strftime("%B %d, %Y at %H:%M UTC") + """</p>
            </div>
        </div>
    </body></html>
    """
    return body

def send_consolidated_notification(aggregated_results: Dict, recipient_emails: List[str], cc_emails: Optional[List[str]] = None) -> bool:
    sender_email = os.environ.get("SENDER_EMAIL")
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not all([sender_email, api_key, recipient_emails]):
        logging.error("Missing required email configuration")
        return False

    found_sources = [source.upper() for source, data in aggregated_results.items() if data]
    today_str = datetime.now().strftime("%Y-%m-%d")

    if not found_sources:
        subject = f"PharmaReg Daily Report: {today_str} - No Updates Found"
    else:
        total_updates = sum(len(data) for data in aggregated_results.values())
        subject = f"PharmaReg Report: {total_updates} New Updates from {', '.join(found_sources)} ({today_str})"

    html_content = format_consolidated_html(aggregated_results)
    message = Mail(from_email=sender_email, to_emails=recipient_emails, subject=subject, html_content=html_content)
    if cc_emails:
        message.cc = cc_emails

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        logging.info(f"Email sent successfully to {len(recipient_emails)} recipients, status: {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    recipients_str = os.environ.get("RECIPIENT_EMAILS", "")
    cc_str = os.environ.get("CC_EMAILS", "")
    if not recipients_str:
        logging.error("RECIPIENT_EMAILS not configured")
    else:
        recipient_list = [e.strip() for e in recipients_str.split(',') if e.strip()]
        cc_list = [e.strip() for e in cc_str.split(',') if e.strip()] if cc_str else None
        test_data = {
            "edqm": [
                {"issue_date_cep": "2025-09-04", "certificate_holder": "MACLEODS PHARMACEUTICALS", "substance": "Nebivolol hydrochloride", "certificate_number": "CEP 2024-172"},
                {"issue_date_cep": "2025-09-02", "certificate_holder": "GLOBAL PHARMA", "substance": "Aspirin", "certificate_number": "CEP 2023-100"},
            ],
            "cdsco": [
                {"release_date": "2025-09-09", "company_name": "M/s Dishman Carbogen Amics", "products": "Benzalkonium Chloride and 6 Items", "download_pdf_link": "#"},
            ],
            "fda": [
                {"posted_date": "2025-09-09", "company_name": "Jalisco Fresh Produce, Inc.", "issuing_office": "Division of West Coast Imports", "letter_url": "#"},
                {"posted_date": "2025-09-08", "company_name": "PharmaTech Solutions LLC", "issuing_office": "CDER", "letter_url": "#"},
            ]
        }
        logging.info("--- Sending FULL Data Test Email ---")
        send_consolidated_notification(test_data, recipient_list, cc_list)

        logging.info("\n--- Sending NO Data Test Email ---")
        send_consolidated_notification({"edqm": [], "cdsco": [], "fda": []}, recipient_list, cc_list)