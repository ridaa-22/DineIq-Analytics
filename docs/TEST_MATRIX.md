# DineIQ test matrix (Phases 1–7, 9–10)

Run from the repository root. This matrix maps executable checks to requirements; it does not claim deployment or uptime evidence. Phase 8 was not requested in this run.

| SRS area | Executable evidence | Coverage limit |
|---|---|---|
| Functional, management | `tests/test_dynamic_app.py` management actions and validation | Isolated SQLite and clean fixture |
| Integration, API/UI | `tests/test_dynamic_app.py`, `tests/browser_phase9_smoke.py` | Browser smoke uses local Chromium |
| Big Data ingestion | `tests/test_phase1_generator.py`, `tests/test_spark_ingestion.py` | Generated fixture, local Spark |
| Schema validation, data quality | `tests/test_cleaning_contract.py`, `tests/run_phase1_acceptance.py` | Hidden external datasets remain untested |
| Spark transformations, SQL | `tests/test_spark_processed_sql.py` | Local Spark execution |
| Spark models | `tests/test_spark_model_persistence.py` | Local persistence/reload environment |
| Python models | `tests/python/test_model_and_leakage.py`, `tests/test_grain_forecast.py` | Historical holdout only |
| Dual pipeline | `tests/test_dynamic_app.py` comparison checks, `tests/test_grain_forecast.py` | Existing fixed case fixture |
| Forecast | `tests/test_grain_forecast.py`, `tests/browser_phase6_smoke.py` | Future recursive forecast accuracy unobserved |
| Basket | `tests/test_business_methods.py`, `tests/test_dynamic_app.py` | Association, not causal lift |
| Wastage | `tests/test_wastage_feature_parity.py`, `tests/test_dynamic_app.py` | Model remains experimental |
| Promotion | `tests/test_campaign_calendar.py`, `tests/test_dynamic_app.py` | Observational comparison |
| Pricing | `tests/test_business_methods.py`, `tests/test_dynamic_app.py` | Observational sensitivity |
| Anomaly | `tests/test_dynamic_app.py` live modules | Statistical flags, no labeled anomalies |
| Security | `tests/test_demo_api.py`, `tests/test_dynamic_app.py` auth/roles/static path | No external penetration test |
| Boundary, hidden-data readiness | `tests/test_cleaning_contract.py`, `tests/test_dynamic_app.py` invalid values, empty period, missing dependency | No claim of exhaustive unseen-data proof |

## Confirmed audit bug regression map

| Bug | Permanent check |
|---|---|
| BUG-01 finite menu inputs | `DynamicAppTests.test_management_rejects_invalid_values_and_references` |
| BUG-02 promotion dates/references | Same management test |
| BUG-03 inventory references | Same management test, including direct FK insertion |
| BUG-04 campaign eligibility | `tests/test_campaign_calendar.py`, `DynamicAppTests.test_item_campaign_what_if_excludes_same_category_item` |
| BUG-05 wastage training/inference parity | `tests/test_wastage_feature_parity.py` |
| BUG-06 cleaner NaN/Infinity/enums/references | `tests/test_cleaning_contract.py` |
| BUG-07 display/export selection | `DynamicAppTests.test_bug_07_filtered_menu_exports_match_api`, `tests/browser_phase9_smoke.py` |
| BUG-08 safe errors | `DynamicAppTests.test_bug_08_safe_filter_errors_and_bounds` |
| BUG-09 Karachi local boundaries | `tests/test_campaign_calendar.py` |
| Legacy static exposure | `DynamicAppTests.test_management_rejects_invalid_values_and_references`, `tests/test_demo_api.py` |

## Filter and error contract

`fast_apis/services/analytics_filters.py` defines typed date, ID, channel, class, rating, and status fields plus the filters each analytical resource accepts. The menu screen and CSV/XLSX exports call `dynamic.menu` with the same selection. `rating` is a minimum average rating. `performance_class` and legacy `classification` are aliases; conflicting values return 422. Unsupported filters sent as declared query fields return 422. Unknown arbitrary query keys may still be ignored by FastAPI.

API errors include `detail` for existing clients and `error: {code, message}`. Authentication/authorization use 401/403, missing resources 404, conflicts 409, structured/domain validation 422, missing processed data/model or database 503. Unexpected failures use a sanitized 500 response; server logs retain diagnostic detail.
