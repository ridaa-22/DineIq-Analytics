# Phase 9–10 local evidence — 2026-09-29

Phase 7 was committed as `d542987 Add scoped multifactor slow-moving intelligence` before Phase 9 work. Phase 9–10 changes are in the working tree; no Phase 9–10 commit was requested.

## Reproduction and fix

Before editing, `GET /api/analytics/menu?category_id=1&limit=200` returned 10 items, while `/api/exports/menu?category_id=1&format=csv` returned 150 rows across categories 1–10. The export route forwarded only `location_id`. The export now calls the same menu service with the selected filters. CSV and XLSX tests compare item IDs for category, location, class, and slow-status combinations. A live Chromium check changes the category, downloads CSV, and compares exported item names to the displayed table.

The frontend now uses same-origin API URLs and displays recommendation evidence. Dashboard category filtering changes its sales cards and scoped item/category wastage cost. Typed dates, finite/bounded IDs, channel, rating, class, and status are validated by the shared filter contract where applicable. The API returns a sanitized `detail` and `error` object on handled errors.

## Executed checks

| Command | Observed result |
|---|---|
| `python -m unittest tests.test_dynamic_app.DynamicAppTests.test_export_is_authenticated_and_audited -v` | 1 passed |
| `python -m unittest tests.test_dynamic_app.DynamicAppTests.test_live_modules tests.test_dynamic_app.DynamicAppTests.test_slow_moving_analysis_is_scoped_and_actionable -v` | 2 passed |
| `python -m unittest tests.test_dynamic_app.DynamicAppTests.test_bug_07_filtered_menu_exports_match_api tests.test_dynamic_app.DynamicAppTests.test_bug_08_safe_filter_errors_and_bounds -v` | 2 passed |
| `python tests/browser_phase9_smoke.py` | Chromium passed: three forecast grains, category export equivalence, recommendation evidence |
| `python -m unittest tests.test_dynamic_app tests.test_demo_api tests.test_campaign_calendar tests.test_cleaning_contract tests.test_wastage_feature_parity tests.test_slow_moving tests.test_grain_forecast -q` | 31 passed |
| `python -m unittest tests.test_spark_processed_sql tests.test_spark_model_persistence -q` | 4 ran, 1 error: native Windows Spark reload fails on Hadoop `NativeIO$Windows.access0` |
| `docker run --rm -u 0 -v "D:\SAAS\DineIQ\DineIq-Analytics:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m unittest tests.test_spark_model_persistence -q` | 1 passed; 3 saved fixture predictions matched |
| `python -m unittest tests.test_dynamic_app.DynamicAppTests.test_bug_08_safe_filter_errors_and_bounds -q` | 1 passed after adding missing-model and unavailable-database cases |
| `node --check DineiqFrantend/template/assets/js/dineiq-demo.js` | Exit 0 |
| `python -m compileall -q fast_apis/routes/dynamic.py fast_apis/routes/exports.py fast_apis/services/analytics_filters.py fast_apis/main.py` | Exit 0 |
| `git diff --check` | Exit 0; line-ending warning only |

## Limits

The menu page displays and exports up to 200 selected rows; the current 150-item dataset fits, but pagination or a streaming export is needed for larger catalogs. Arbitrary unknown query keys are still ignored by FastAPI; declared unsupported filter fields return 422. The category-filtered dashboard's wastage cost uses item/category/date/location scope; channel and campaign do not apply to wastage records. The Windows Spark reload limitation remains; the pinned Linux Docker test passed. This run did not execute a full external hidden-data suite or deployment/uptime tests.
