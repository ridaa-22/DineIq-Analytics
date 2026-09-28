# DineIQ Analytics

FastAPI serves the authenticated restaurant analytics app at `http://127.0.0.1:8000/app/Login.html`. Current analytics read versioned cleaned Parquet; SQLite stores users, roles, business metadata, recommendations, model versions, jobs, and audit events. The 1,000,000-line raw synthetic dataset is retained separately.

## Start on Windows PowerShell

Run from this repository root. Python 3.13 is the currently tested interpreter. Spark also needs a working local Java installation.

```powershell
python -m pip install -r requirements-demo.txt
python -m Python_Pipeline.build_processed
python -m Python_Pipeline.build_basket_rules
python -m Python_Pipeline.train_location_forecast
python -m Python_Pipeline.train_customer_segments
python -m Python_Pipeline.train_wastage_forecast
python -m pip install -r requirements-spark.txt
python -m spark_jobs.processed_sql
python -m spark_jobs.train_location_forecast
python -m Python_Pipeline.compare_location_forecasts
python -m scripts.seed_demo_accounts
python -m uvicorn fast_apis.main:app --host 127.0.0.1 --port 8000
```

The raw `data/raw/phase1-v1` dataset must exist before building processed data. To generate it in a fresh checkout, run `python -B data_generator/generate_phase1.py` once; this refuses to overwrite an existing output. Spark's native model save currently fails on this Windows machine because Hadoop `winutils.exe` is absent. The Spark prediction export and evaluation still run; see [limitations](docs/LIMITATIONS.md).

Open [http://127.0.0.1:8000/app/Login.html](http://127.0.0.1:8000/app/Login.html). Local role credentials are generated in ignored `data/demo_credentials.json`. Existing accounts are preserved and passwords are not reset. Rotate passwords before sharing an environment.

Tests:

```powershell
python -m unittest tests.test_demo_api tests.test_dynamic_app tests.test_business_methods -v
node --check DineiqFrantend/template/assets/js/dineiq-demo.js
```

The legacy Express server is unnecessary for this application path. FastAPI serves the frontend at `/app/`.

Read [API](docs/API.md), [roles](docs/ROLES.md), [runbook](docs/RUNBOOK.md), [data dictionary](docs/DATA_DICTIONARY.md), [current SRS audit](docs/CURRENT_SRS_REAUDIT.md), and [limitations](docs/LIMITATIONS.md) before interpreting analytical outputs.
