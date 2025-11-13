cd pharma-reg-monitor
pip install -r requirements.txt
python -m src.sources.edqm_source
python -m src.sources.cdsco_source
python -m src.sources.fda_source
python -m src.sources.fda_dmf_source

python -m src.consolidate_results
python -m src.generate_email_html
python -m src.send_email_notification

python -m src.manager