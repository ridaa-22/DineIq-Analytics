# Phase 6: grain and horizon forecasts

The existing independent 581-case Python/Spark location comparison remains a one-step observed-lag evaluation. Its Python training now also measures a chronological Nov 3–Dec 2 validation period before refitting on train plus validation for the Dec 3–Jan 1 test. The comparison still reports 581 cases, Python MAE 70.4840, Spark MAE 79.2460, and 86.2306% agreement.

The new common implementation is `Python_Pipeline/forecast_features.py` plus `train_grain_forecasts.py`. It builds location, item, and category daily quantity demand from the clean `phase1-v1` snapshot. Active days without sales are zero; item 9 begins on its introduction date, rather than receiving false pre-introduction zeros. Lag 1, lag 7, and seven-day average are shifted before feature construction. The only other predictors are entity ID and known calendar fields. No promotion or price feature is used. The same feature order and recursive prediction function serve training backtests and API inference.

The daily series contain 7,320 location-days, 54,566 active item-days, and 3,660 category-days. Each grain sums to the same 1,324,869 sold portions, so the aggregation does not multiply demand.

Each grain trains an earlier Random Forest, evaluates recursive validation from Nov 2, refits through Dec 2, and evaluates a separate recursive test origin on Dec 3 through Jan 1. For lead 7, 14, and 30, preceding forecast values replace unknown future demand in both the model and seasonal lag-7 baseline. Exact-lead metrics average across eligible entities at that one origin. Item 9 lacks seven pre-test days and is excluded from test metrics; it can receive current forecasts after its observed history reaches seven days.

| Grain | Test cases per lead | Lead 1 MAE / baseline | Lead 7 MAE / baseline | Lead 14 MAE / baseline | Lead 30 MAE / baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
| Location | 20 | 49.55 / 106.45 | 50.85 / 76.00 | 42.06 / 62.35 | 226.65 / 128.95 |
| Item | 149 | 11.36 / 15.07 | 9.40 / 7.11 | 9.95 / 7.34 | 26.68 / 17.31 |
| Category | 10 | 99.29 / 205.10 | 99.12 / 35.20 | 113.10 / 34.30 | 460.84 / 257.90 |

The new `/api/analytics/forecast` grain parameters return future rows with `Actual: null`, or held-out backtest rows with actuals. Each response includes grain, entity, horizon, model and dataset versions, exact-lead test MAE and baseline MAE, and `EXPERIMENTAL` status. The existing default route behavior remains available. The Forecast & Models browser view has selectors for grain, entity, horizon, and future/backtest.

Executed from the repository root:

```powershell
python -m Python_Pipeline.train_grain_forecasts
python -m Python_Pipeline.train_location_forecast
python -m Python_Pipeline.compare_location_forecasts
python -c "from Python_Pipeline.forecast_features import daily_series; print({g:(len(daily_series(g)),int(daily_series(g).Demand.sum())) for g in ('location','item','category')})"
python -m pytest tests/test_grain_forecast.py tests/test_dynamic_app.py -q
node --check DineiqFrantend/template/assets/js/dineiq-demo.js
python tests/browser_phase6_smoke.py
```

The first focused pytest run found FastAPI's integer `Literal` query parsing issue and failed 1 test; replacing it with bounded integer input and explicit allowed-horizon validation made the targeted rerun pass. The final focused and relevant regression suite passed 25 tests with one Starlette deprecation warning. The browser test initially exposed a hard-coded port 8000 in the JavaScript. After using the served `/app/` origin, headless Chromium submitted and rendered `location:1`, `item:7`, and `category:30` requests through a live local API backed by a temporary authentication database. The browser executable was installed locally; no deployment or uptime is implied.
