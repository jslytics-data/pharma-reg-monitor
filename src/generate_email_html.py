import os
import json
import logging
import glob
from datetime import datetime
from urllib.parse import quote_plus
from typing import Dict, List, Optional

def _sort_data_by_date(data: list, date_key: str) -> list:
    try:
        return sorted(
            data,
            key=lambda x: datetime.strptime(x.get(date_key, '1900-01-01'), '%Y-%m-%d'),
            reverse=True
        )
    except (ValueError, TypeError):
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

def _format_dmf_section(report_data: Dict) -> str:
    dmf_info = report_data.get("fda_dmf", {})
    dmf_date_str = dmf_info.get("update_date")
    download_url = dmf_info.get("download_url", "#")
    page_url = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"

    if not dmf_date_str:
        return ""
    try:
        date_obj = datetime.strptime(dmf_date_str, '%Y-%m-%d')
        days_since_update = (datetime.now() - date_obj).days
        formatted_date = date_obj.strftime('%B %d, %Y')
        icon, bg_color, border_color, status_text, text_color = ("🆕", "#fef3c7", "#fbbf24", "Recently Updated", "#92400e") if days_since_update <= 7 else ("📋", "#f9fafb", "#e5e7eb", "Current Status", "#6b7280")
        
        return f"""
        <tr><td style="padding: 24px 20px;"><table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;"><tr><td style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 16px;"><table border="0" cellpadding="0" cellspacing="0" width="100%"><tr><td width="32" style="font-size: 20px; padding-right: 12px;">{icon}</td><td><p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">FDA DMF LIST • {status_text}</p><p style="margin: 4px 0 0 0; font-size: 14px; color: #374151;">Last updated: {formatted_date}<a href="{page_url}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 500; margin-left: 12px;">View Page →</a><a href="{download_url}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 500; margin-left: 12px;">Download →</a></p></td></tr></table></td></tr></table></td></tr>
        """
    except (ValueError, TypeError):
        return ""

def _format_summary_section(report_data: Dict) -> str:
    sources, source_info_map = [], {'edqm': {'icon': '🇪🇺', 'name': 'EDQM', 'color': '#3b82f6'},'cdsco': {'icon': '🇮🇳', 'name': 'CDSCO', 'color': '#f59e0b'},'fda': {'icon': '🇺🇸', 'name': 'FDA', 'color': '#ef4444'}}
    for name, info in report_data.items():
        if isinstance(info, dict) and info.get("update_count", 0) > 0:
            count, meta = info["update_count"], source_info_map.get(name, {})
            sources.append(f'<td style="text-align: center; padding: 0 8px;"><div style="font-size: 24px; margin-bottom: 4px;">{meta.get("icon", "•")}</div><div style="font-size: 28px; font-weight: 700; color: {meta.get("color", "#6b7280")}; margin-bottom: 2px;">{count}</div><div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">{meta.get("name", name.upper())}</div></td>')
    if not sources: return '<tr><td style="padding: 24px 20px;"><div style="background-color: #f9fafb; border-radius: 12px; padding: 32px; text-align: center;"><p style="font-size: 16px; color: #6b7280; margin: 0;">No new updates found in the monitored sources.</p></div></td></tr>'
    return f'<tr><td style="padding: 0 20px 24px 20px;"><div style="background-color: #fafafa; border-radius: 12px; padding: 24px;"><p style="font-size: 14px; color: #6b7280; margin: 0 0 16px 0; text-align: center; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Summary of Updates</p><table border="0" cellpadding="0" cellspacing="0" width="100%"><tr>{"".join(sources)}</tr></table></div></td></tr>'

def _create_section(title_icon: str, title_text: str, source_info: Dict, color: str, headers: List[str], row_formatter) -> str:
    count = source_info.get("update_count", 0)
    source_url = source_info.get("source_url", "#")
    updates = source_info.get("updates", [])
    rows_html = "".join(row_formatter(item, i, color) for i, item in enumerate(updates))
    header_html = "".join(f'<th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase;">{h}</th>' for h in headers)
    header_html += '<th style="width:20px;"></th>'
    return f"""
    <tr><td style="padding-bottom: 24px;"><div style="padding: 20px 20px 0 20px;"><table border="0" cellpadding="0" cellspacing="0" width="100%"><tr><td><h2 style="font-size: 18px; color: #1f2937; margin: 0; font-weight: 600;">{title_icon} {title_text}</h2></td><td style="text-align: right;"><span style="background-color: {color}; color: #ffffff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 999px; text-decoration: none;">{count} NEW</span><a href="{source_url}" target="_blank" style="font-size: 12px; color: #667eea; text-decoration: none; margin-left: 12px; font-weight: 500;">View Source →</a></td></tr></table></div><div style="margin: 16px 10px 0 10px; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb;"><table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;"><thead><tr style="background-color: #f9fafb; border-bottom: 1px solid #e5e7eb;">{header_html}</tr></thead><tbody>{rows_html}</tbody></table></div></td></tr>
    """

def _format_edqm_section(source_info: Dict) -> str:
    source_info["updates"] = _sort_data_by_date(source_info.get("updates", []), 'issue_date_cep')
    def formatter(item, i, color):
        date_str = datetime.strptime(item.get('issue_date_cep'), '%Y-%m-%d').strftime('%b %d') if item.get('issue_date_cep') else 'N/A'
        holder = item.get('certificate_holder', 'N/A'); substance = item.get('substance', 'N/A'); cert_num = item.get('certificate_number', 'N/A')
        bg_color = "#ffffff" if i % 2 == 0 else "#fafafa"
        return f'<tr style="background-color: {bg_color};"><td style="padding: 10px; font-size: 13px; color: #6b7280; white-space: nowrap;">{date_str}</td><td style="padding: 10px; font-size: 14px; color: #374151; font-weight: 500;">{holder[:40]}{"..." if len(holder) > 40 else ""}</td><td style="padding: 10px; font-size: 13px; color: #6b7280;">{substance[:25]}{"..." if len(substance) > 25 else ""}</td><td style="padding: 10px; font-size: 11px; color: #6b7280; font-family: \'Courier New\', monospace; text-align: left;">{cert_num}</td><td style="padding: 10px; text-align: right;"><a href="{item.get("monograph_url", "#")}" target="_blank" style="color: {color}; text-decoration: none; font-size: 18px; font-weight: bold;">→</a></td></tr>'
    return _create_section("🇪🇺", "EDQM Certificates", source_info, "#3b82f6", ["Date", "Holder", "Substance", "Cert #"], formatter)

def _format_cdsco_section(source_info: Dict) -> str:
    source_info["updates"] = _sort_data_by_date(source_info.get("updates", []), 'release_date')
    def formatter(item, i, color):
        date_str = datetime.strptime(item.get('release_date'), '%Y-%m-%d').strftime('%b %d') if item.get('release_date') else 'N/A'
        company = item.get('company_name', 'N/A'); products = item.get('products', 'N/A')
        bg_color = "#ffffff" if i % 2 == 0 else "#fafafa"
        return f'<tr style="background-color: {bg_color};"><td style="padding: 10px; font-size: 13px; color: #6b7280; white-space: nowrap;">{date_str}</td><td style="padding: 10px; font-size: 14px; color: #374151; font-weight: 500;">{company[:35]}{"..." if len(company) > 35 else ""}</td><td style="padding: 10px; font-size: 13px; color: #6b7280;">{products[:40]}{"..." if len(products) > 40 else ""}</td><td style="padding: 10px; text-align: right;"><a href="{item.get("download_pdf_link", "#")}" target="_blank" style="color: {color}; text-decoration: none; font-size: 18px; font-weight: bold;">→</a></td></tr>'
    return _create_section("🇮🇳", "CDSCO Written Confirmations", source_info, "#f59e0b", ["Date", "Company", "Products"], formatter)

def _format_fda_section(source_info: Dict) -> str:
    source_info["updates"] = _sort_data_by_date(source_info.get("updates", []), 'posted_date')
    def formatter(item, i, color):
        date_str = datetime.strptime(item.get('posted_date'), '%Y-%m-%d').strftime('%b %d') if item.get('posted_date') else 'N/A'
        company = item.get('company_name', 'N/A'); office = item.get('issuing_office', 'N/A')
        bg_color = "#ffffff" if i % 2 == 0 else "#fafafa"
        return f'<tr style="background-color: {bg_color};"><td style="padding: 10px; font-size: 13px; color: #6b7280; white-space: nowrap;">{date_str}</td><td style="padding: 10px; font-size: 14px; color: #374151; font-weight: 500;">{company[:40]}{"..." if len(company) > 40 else ""}</td><td style="padding: 10px; font-size: 13px; color: #6b7280;">{office[:30]}{"..." if len(office) > 30 else ""}</td><td style="padding: 10px; text-align: right;"><a href="{item.get("letter_url", "#")}" target="_blank" style="color: {color}; text-decoration: none; font-size: 18px; font-weight: bold;">→</a></td></tr>'
    return _create_section("🇺🇸", "FDA Warning Letters", source_info, "#ef4444", ["Date", "Company", "Office"], formatter)

def generate_html_report(consolidated_report: Dict) -> Optional[Dict[str, str]]:
    if not isinstance(consolidated_report, dict):
        logging.error("HTML Generator: Invalid data type for consolidated_report, expected dict.")
        return None
    
    today_str = datetime.now().strftime("%B %d, %Y")
    total_updates = consolidated_report.get("total_updates", 0)
    subject = f"PharmaReg Intelligence | {total_updates} New Updates - {today_str}" if total_updates > 0 else f"PharmaReg Intelligence | {today_str} - No Updates"

    body_sections = [_format_header_section(), _format_dmf_section(consolidated_report), _format_summary_section(consolidated_report)]
    source_formatters = {"edqm": _format_edqm_section, "cdsco": _format_cdsco_section, "fda": _format_fda_section}
    
    for source, data in consolidated_report.items():
        if isinstance(data, dict) and data.get("update_count", 0) > 0:
            if source in source_formatters:
                body_sections.append(source_formatters[source](data))
    
    html_template = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>PharmaReg Intelligence Report</title></head><body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased;"><table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f3f4f6;"><tr><td align="center" style="padding: 40px 0;"><table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06); overflow: hidden;">
    {body_content}
    <tr><td style="padding: 24px; background-color: #f9fafb; border-top: 1px solid #e5e7eb;"><p style="font-size: 12px; color: #9ca3af; margin: 0; text-align: center;">© 2025 PharmaReg Intelligence • Automated Regulatory Monitoring</p></td></tr>
    </table></td></tr></table></body></html>
    """
    
    html_body = html_template.format(body_content="".join(body_sections))
    return {"subject": subject, "html_body": html_body}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    EXPORT_DIR = "exports"
    
    try:
        list_of_files = glob.glob(os.path.join(EXPORT_DIR, "consolidated_report_*.json"))
        if not list_of_files:
            raise FileNotFoundError("No consolidated report files found in exports/.")
        latest_file = max(list_of_files, key=os.path.getctime)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        logging.info(f"Loaded data from {os.path.basename(latest_file)}")

        email_package = generate_html_report(report_data)
        if email_package:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"email_preview_{timestamp}.html"
            filepath = os.path.join(EXPORT_DIR, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(email_package["html_body"])
            logging.info(f"SUCCESS: Email HTML generated and saved to {filepath}")
            logging.info(f"Subject: {email_package['subject']}")
        else:
            logging.error("FAILED: HTML generation returned None.")
            
    except (FileNotFoundError, IndexError, json.JSONDecodeError) as e:
        logging.error(f"Test run failed: Could not load test data. {e}")