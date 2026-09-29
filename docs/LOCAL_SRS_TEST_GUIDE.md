# Local run and SRS verification guide

Run commands in **PowerShell** from `D:\SAAS\DineIQ\DineIq-Analytics`. Replace that path if your checkout differs. This guide describes the current local app; it does not turn the historical 2026-09-28 audit statuses into completion claims. Read the [test matrix](TEST_MATRIX.md), [NFR evidence](NFR_EVIDENCE.md), and [limits](LIMITATIONS.md) when judging results.

## 1. Start the existing app (fastest path)

Open PowerShell in the repository root:

```powershell
Set-Location 'D:\SAAS\DineIQ\DineIq-Analytics'
python --version
java -version
python -m pip install -r requirements-demo.txt
python -m pip install -r requirements-spark.txt
Test-Path data/raw/phase1-v1/manifest.json
Test-Path data/processed/phase1-v1/quality_report.json
Test-Path Models/integrated/python_forecast.joblib
python -m scripts.seed_demo_accounts
Get-Content data/demo_credentials.json
python -m uvicorn fast_apis.main:app --host 127.0.0.1 --port 8000
```

Leave that terminal open. Open `http://127.0.0.1:8000/app/Login.html` in a browser and sign in with a generated account from `data/demo_credentials.json`. The file is ignored by Git; keep its passwords private. `seed_demo_accounts` creates missing accounts **once**; it does not reset passwords or recreate the credentials file for existing accounts. If that file is absent because accounts already exist, use an existing password, or use a fresh isolated SQLite database by setting `$env:DINEIQ_AUTH_DB` to a new file path **before** seeding and starting the server. Do not remove an existing app database merely to recover demo credentials.

Self-registration at `/app/register.html` requires a username of 2–80 characters and a password of 8–128 characters. The form now checks those limits before sending; the API returns a field-specific 422 if an invalid request still reaches it. **Self-registration always creates an Analyst account.** Entering `admin` as the username does not grant the Admin role; use the seeded Admin account or have an Admin assign a role through the supported management flow.

For a quick service check in a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

The active frontend is served by FastAPI under `/app/`. Do not open the HTML files with `file://` or start the retired Express server. `data-tables.html` and `project-docs.html` contain old template material and are **not** proof of live operations or SRS completion.

## 2. Rebuild artifacts only when needed

Existing raw data and artifacts are preserved. A fresh checkout missing `data/raw/phase1-v1/manifest.json` can generate the raw version once; the generator refuses an existing output directory:

```powershell
python -B data_generator/generate_phase1.py
```

When you intentionally want to regenerate derived artifacts from that raw version, run sequentially:

```powershell
python -m Python_Pipeline.build_processed
python -m spark_jobs.ingest
python -m spark_jobs.processed_sql
python -m Python_Pipeline.build_basket_rules
python -m Python_Pipeline.train_location_forecast
python -m Python_Pipeline.train_grain_forecasts
python -m Python_Pipeline.train_customer_segments
python -m Python_Pipeline.train_wastage_forecast
python -m scripts.refresh_slow_moving_evidence
```

For the selected **persisted Spark model**, use the documented Linux Docker runtime; native Windows `save/load` still fails on Hadoop `NativeIO$Windows.access0`:

```powershell
docker build -t dineiq-spark:4.0.2 -f docker/spark/Dockerfile .
docker run --rm -u 0 -v "${PWD}:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m spark_jobs.train_location_forecast
docker run --rm -u 0 -v "${PWD}:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m scripts.reload_spark_location_forecast
python -m Python_Pipeline.compare_location_forecasts
python -m scripts.seed_demo_accounts
```

Use separate Docker commands: the reload must be a fresh process. On Windows PowerShell, Docker Desktop must be running with Linux containers and permission to mount the checkout. The PySpark training commands are work-heavy and rewrite derived model/report files; skip this section if the committed/local artifacts are already present and you only want a browser walkthrough.

## 3. Browser walkthrough

The live quick navigation appears at the top of the rendered app. Use these exact pages after login:

| View | Browser URL | What to try |
|---|---|---|
| Executive | `/app/index.html` | Change location and category; cards should change. |
| Orders | `/app/operations-orders.html` | Date/channel/status filters, pagination, cancelled-order revenue note. |
| Menu intelligence | `/app/menu-management.html` | Category/class/slow-status filters; compare rows with CSV/Excel export buttons. |
| Customers | `/app/customer-segments.html` | Segment filter, cluster profiles, RFM rows. |
| Wastage | `/app/index.html?view=wastage` | Wastage totals, item/location rows, next-week experimental risk. |
| Forecast & models | `/app/analytics-ml.html` | Location/item/category grain, entity ID, horizon 1/7/14/30, future/backtest, model comparison, next-day location estimate. |
| Promotions | `/app/index.html?view=promotions` | Campaign economics and trap flag. |
| Pricing | `/app/index.html?view=pricing` | Historical price event comparison. |
| Basket | `/app/index.html?view=basket` | Pair support, confidence, lift; global view is forbidden to Regional Manager. |
| Channels/locations | `/app/index.html?view=channels`, `/app/index.html?view=locations` | Compare revenue/contribution and location ranks. |
| Anomalies/rating flags | `/app/index.html?view=anomalies`, `/app/index.html?view=rating-anomalies` | Inspect flagged rows; these are statistical flags, not confirmed fraud. |
| Churn | `/app/index.html?view=churn` | At-risk customers and recency/decline evidence. |
| Recommendations | `/app/index.html?view=recommendations` | Action, reason, priority, entity, and evidence column. |
| What-if | `/app/index.html?view=what-if` | Enter an item, demand assumption, price/discount changes; result is an estimate. |
| Reports | `/app/reports.html` | Download current CSV/Excel exports; regional exports remain location scoped. |
| Management | `/app/index.html?view=admin` | Admin/Manager create or edit metadata. Admin also manages users/locations. Writes do not automatically rebuild historical Parquet or retrain models. |
| Jobs | `/app/index.html?view=jobs` | Admin can start an allow-listed job and watch status; other roles can inspect recorded jobs. |

Use the **Admin**, **Manager**, **Regional Manager**, and **Analyst** accounts in separate private windows or sign out between roles. The Regional Manager demo account is assigned locations 1 and 2, so it cannot prove an out-of-scope denial by selecting location 2; use an unassigned location (for example 3) or run the isolated role browser test, which assigns only location 1. The Analyst can read analytics but cannot write management data. Manager can edit menu/promotion/inventory metadata but cannot manage users/locations. Admin can do both.

### Useful direct API checks in the browser

Open `http://127.0.0.1:8000/docs` for the interactive FastAPI schema. Click **Authorize** and enter `Bearer <token>` from an authenticated account if needed. The app stores the local token in browser `localStorage.authToken`; do not share it. Test a few read-only URLs in the docs or authenticated browser session:

```text
/api/analytics/menu?category_id=1&limit=200
/api/exports/menu?category_id=1&format=csv
/api/analytics/slow-moving?category_id=1
/api/analytics/forecast?grain=item&entity_id=4&horizon=7&mode=backtest
/api/models/comparison?limit=20
/api/analytics/promotions
```

Browser navigation to a protected API URL without an `Authorization` header should return 401. Use the app buttons or `/docs` authorization for authenticated calls. For a bad date or unknown reference, expect 422 or 404 with a sanitized `detail`/`error` body rather than a traceback.

## 4. Requirement-by-requirement evidence path

`UI` means a live browser view. `API/test` or `artifact` is required when a browser table cannot prove the underlying calculation. “Partial” describes a remaining gap, not a failed click. The FR labels follow `docs/CURRENT_SRS_REAUDIT.md` section 1.6; that document's baseline counts are historical.

| FR | SRS requirement | Where to see/test | Proof limit |
|---:|---|---|---|
| 1 | Registration/authentication | `/app/register.html`, `/app/Login.html`; try a short and valid password, then sign out; `tests/test_dynamic_app.py` | New public accounts are Analyst; JWT lifecycle is API-tested. |
| 2 | Role access control | Sign in as four roles; try Manage/Reports; `tests/browser_nfr_roles.py` | API 401/403 and scope are decisive. |
| 3 | Location management | Admin `?view=admin` location form; `/api/locations` | Admin-only writes; historical refresh separate. |
| 4 | Menu management | Manager/Admin `?view=admin` item/category forms | Menu intelligence page is analytical, not the edit form. |
| 5 | Pricing history | `?view=pricing`, Admin/Manager item price edit, `/api/pricing/history` | Only observed price-change events support sensitivity. |
| 6 | Anonymized customer profiles | Customer page and `/api/analytics/customers` | Raw customer names exist; full profile anonymity/management remains partial. |
| 7 | Order headers and lines | Orders page; raw CSV and clean Parquet | Browser samples/paginates; use data tests for full relationships. |
| 8 | Promotion management | Admin/Manager `?view=admin`; `?view=promotions` | Coupon workflow and automatic refresh are incomplete. |
| 9 | Rating management | Menu rating column, `?view=rating-anomalies` | No full ratings management UI/API. |
| 10 | Inventory management | Admin/Manager `?view=admin` inventory form | Period records exist; planning is limited. |
| 11 | Wastage records | `?view=wastage`; management form | Live overlay is not model retraining. |
| 12 | Spark ingestion | No UI; `python -m spark_jobs.ingest`, ingestion report | Check typed row counts, schema, provenance. |
| 13 | Schema/relationship validation | No UI; quality report, `tests/test_cleaning_contract.py`, `tests/test_spark_ingestion.py` | Some cross-entity checks remain partial. |
| 14 | Data-quality analysis | No UI; `data/processed/phase1-v1/quality_report.json` | Condition counts may overlap. |
| 15 | Documented cleaning | No UI; quality report and `rejections.jsonl` | Review rule, reason, record ID, action. |
| 16 | Spark SQL | No UI; `python -m spark_jobs.processed_sql`, `Reports/processed_spark/` | Check row and financial reconciliation. |
| 17 | Large-data partitioning | No UI; `sales_by_location/`, `partition_strategy.json` | 20 location partitions in current data. |
| 18 | Processed Parquet | No UI; `data/processed/phase1-v1/*.parquet` | Inspect clean manifest/hash and row counts. |
| 19 | Derived business/ML features | Forecast view plus `forecast_features.py` and tests | Browser cannot establish leak safety alone. |
| 20 | Profitability | Executive and Menu views | Check net revenue, cost, contribution against clean reports/tests. |
| 21 | Menu classes | Menu class filter and class column | Descriptive rules; no supervised class ground truth. |
| 22 | Peak periods | `Reports/processed_spark/peaks.csv` | Full peak dimensions are not integrated in current UI. |
| 23 | Customer segmentation | Customer page: segments and cluster profiles | KMeans artifact/tests prove training. |
| 24 | RFM | Customer page: recency, frequency, net monetary | Clean completed-order basis in tests. |
| 25 | Market basket | `?view=basket` | Regional users cannot open global rules. |
| 26 | Support/confidence/lift | Basket table columns | Compare persisted basket rules and tests. |
| 27 | Bundle recommendations | `?view=recommendations` type `bundle` | Associations are observational. |
| 28 | Future demand forecasting | Forecast view: grain/entity/horizon/future | Future actuals are unavailable; long horizons experimental. |
| 29 | Forecast evaluation | Forecast backtest and model comparison | See chronological metrics and baselines in artifacts. |
| 30 | Wastage trends | Wastage view | Time trend coverage remains partial. |
| 31 | Wastage prediction | Wastage view: next-week high-risk estimates | Experimental: amount model loses to baseline; low high-risk recall. |
| 32 | Price sensitivity | `?view=pricing` | Observational, limited genuine price events. |
| 33 | Promotion effectiveness | `?view=promotions` before/during/after fields | Verify campaign eligibility/timezone with tests. |
| 34 | Promotion trap | `?view=promotions` Trap column | Sales-up/contribution-down flag; no causal claim. |
| 35 | Rating analysis | Menu rating column | Broader rating/performance context is partial. |
| 36 | Rating anomalies | `?view=rating-anomalies` | Statistical burst flags only. |
| 37 | Sales anomalies | `?view=anomalies` | Inspect flagged location/day rows. |
| 38 | Location comparison | `?view=locations`, Executive location filter | Scope and standardized KPIs; broader context partial. |
| 39 | Location-specific menu | Menu location selector | Compare same item under two allowed locations. |
| 40 | Channel analysis | `?view=channels`, Orders channel filter | Completed-sales channel comparison. |
| 41 | Churn risk | `?view=churn` | Rule-based recency/decline, not observed future churn. |
| 42 | Three Spark MLlib algorithms | No UI; `Models/integrated/spark_selection_metrics.json` | Linear/Tree/Forest tested; saved model reload in Docker. |
| 43 | Independent Python ML | Forecast/Customer/Wastage views and model artifacts | Models trained independently; inspect metrics. |
| 44 | Dual prediction comparison | Forecast & Models table | Same 581 unseen cases; compare case IDs/actuals. |
| 45 | Agreement/disagreement | Forecast & Models Difference/Match columns | Fixed 50-unit tolerance; not model equivalence. |
| 46 | Model evaluation | Forecast metrics and `docs/NFR_EVIDENCE.md` | Spark/wastage baselines unfavorable. |
| 47 | Recommendation engine | `?view=recommendations` | Evidence/reason visible; rules are deterministic. |
| 48 | Menu optimization actions | Recommendations and Menu action column | Action set remains partial. |
| 49 | Inventory recommendations | Recommendations type `inventory` | Experimental wastage forecast limits reliability. |
| 50 | Customer targeting | Recommendations type `customer_targeting` | Segment strategies remain partial. |
| 51 | What-if | `?view=what-if` form | Demand change is user supplied; no causal elasticity claim. |
| 52 | Executive dashboard | `/app/index.html` | Category/location-filtered core KPIs; not every SRS card. |
| 53 | Menu dashboard | `/app/menu-management.html` | Filter, table, slow-status, export; broader UX partial. |
| 54 | Customer dashboard | `/app/customer-segments.html` | RFM and KMeans profiles visible. |
| 55 | Wastage dashboard | `?view=wastage` | Totals/records/prediction visible; trend coverage partial. |
| 56 | Forecast dashboard | `/app/analytics-ml.html` | Future/backtest, grain/horizon; long-range quality weak. |
| 57 | Dual pipeline dashboard | `/app/analytics-ml.html` | Python/Spark rows, metrics, version, agreement. |
| 58 | Search/filtering | Executive, Orders, Menu, Customers | Supported filters vary by endpoint; not universal search. |
| 59 | Downloadable reports | `/app/reports.html` | Authenticated report download. |
| 60 | Data export | Menu filtered CSV/Excel buttons; Reports page | Compare selected row set with export; `tests/browser_phase9_smoke.py`. |
| 61 | Database storage | No full UI; management/jobs/recommendation/audit APIs and SQLite | Historical analytics live in Parquet, not SQLite. |
| 62 | Model versions | Forecast response and `?view=jobs` | Check version and dataset version fields. |
| 63 | Audit trail | Admin `?view=admin` recent audit, `/api/audit-logs` | Check after login, export, write, prediction. |
| 64 | Error handling | Bad form/query via `/docs`; `tests/test_dynamic_app.py` | Safe 4xx/503 contract; not every infrastructure failure simulated. |
| 65 | Spark job monitoring | Admin `?view=jobs`: start/poll/status | Windows Spark save may warn; Docker persistence separate. |
| 66 | Responsive interface | Chromium desktop/mobile browser test | Tested 1366×768 and 390×844 only; other browsers unverified. |

## 5. Automated verification commands

Run focused checks from the repository root. The browser scripts launch a temporary local API and use Chromium/Chrome through Playwright; install Playwright/Chromium first if absent. These tests create isolated auth databases and do not replace your app database.

```powershell
python -m pip install pytest playwright
python -m playwright install chromium
python -m unittest tests.test_nfr_scale tests.test_phase1_generator -q
python -m unittest tests.test_dynamic_app tests.test_demo_api tests.test_campaign_calendar tests.test_cleaning_contract tests.test_wastage_feature_parity tests.test_slow_moving tests.test_grain_forecast -q
python -m unittest tests.test_spark_ingestion tests.test_spark_processed_sql -q
python tests/browser_phase9_smoke.py
python tests/browser_nfr_roles.py
node --check DineiqFrantend/template/assets/js/dineiq-demo.js
```

Run Spark persistence verification in the supported Docker runtime:

```powershell
docker run --rm -u 0 -v "${PWD}:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m unittest tests.test_spark_model_persistence -q
```

NFR measurements and the 5M scale fixture are **optional heavy checks**, not needed to browse the app. They write to `Reports/nfr_scale/` and `Reports/nfr_*.json`; the 5M temporary fixture is ignored by Git. The full SQL run needs a 4 GB Spark driver heap on this host and failed at the default heap:

```powershell
python -m scripts.evaluate_nfr_baselines
python -m scripts.benchmark_nfr
python -m scripts.availability_smoke
python -m scripts.make_scale_fixture --factor 5 --output Reports/nfr_scale/raw_5m
python -m spark_jobs.ingest --data-root Reports/nfr_scale/raw_5m --report Reports/nfr_scale/ingestion_summary.json
python -c "from pathlib import Path; import Python_Pipeline.build_processed as m; m.RAW=Path('Reports/nfr_scale/raw_5m').resolve(); m.OUT=Path('Reports/nfr_scale/processed_5m').resolve(); m.build()"
$env:SPARK_DRIVER_MEMORY='4g'
python -c "from pathlib import Path; from spark_jobs.processed_sql import run; run(Path('Reports/nfr_scale/processed_5m').resolve(), Path('Reports/nfr_scale/spark_sql_5m').resolve())"
```

The scale generator refuses to overwrite an existing output directory. Use a new fixture directory name for a repeat; do not delete the authoritative raw data. A short local health-check sample is **not** evidence of 99% uptime. The SRS five-second wording still needs interpretation, and the saved Spark and wastage forecast baselines are not favorable.
