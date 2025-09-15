cd pharma-reg-monitor
pip install -r requirements.txt
python -m src.sources.edqm_source
python -m src.sources.cdsco_source
python -m src.sources.fda_source
python -m src.sources.fda_dmf_source
python -m src.data_aggregator
python -m src.notifier
python -m src.manager