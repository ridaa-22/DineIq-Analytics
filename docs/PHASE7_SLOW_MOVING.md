# Phase 7: multifactor slow-moving analysis

The forensic audit found no slow-moving status in the active menu, recommendation, or current report paths. The shared rule in `Python_Pipeline/slow_moving.py` now assesses the same clean scoped menu summary used by the API. It does not change the existing four descriptive menu classes.

For each global or location scope, the rule considers sales-volume percentile, orders per 30 available days and its percentile, days since last completed sale, recent versus prior 30-day trend, repeat purchase rate, contribution and margin rank, observed wastage percentage, introduction age, and monthly volume concentration. The `Evidence` field records those values and the scope. Category filters are applied after scoring, so they do not change an item's status.

Decisions, in order:

1. Fewer than 90 days since recorded introduction: `INSUFFICIENT_HISTORY`.
2. No observed sales in an established scope: `NO_OBSERVED_SALES`, with an availability check before calling demand slow.
3. At least 180 days of history, four selling months, and at least 70% of volume in the top three months: `SEASONAL_REVIEW`. One synthetic year cannot prove recurring seasonality.
4. Bottom 35% for volume, positive contribution, top 40% for margin, and quality or positive momentum: `HIDDEN_OPPORTUNITY`.
5. Bottom 35% for both volume and order frequency, a decline of at least 20% or 30 days without a sale, and weak repeats or economics: `SLOW_MOVER`. Severity rises with more severe recency, trend, or wastage.
6. Low volume and frequency with weak repeats or economics but without confirmed demand decline: `WATCHLIST`.
7. Otherwise: `NOT_SLOW`.

These are review rules rather than learned or causal labels. `Recommended_Action` asks for visibility, stock, preparation, or seasonal review before removal. The same result appears in Menu Intelligence, `/api/analytics/slow-moving`, recommendations, the scoped CSV/Excel export, and `Reports/CURRENT_RESTAURANT_INTELLIGENCE.md`. The current global CSV is `Reports/CURRENT_SLOW_MOVING.csv`.

The current global clean snapshot has 150 items: 98 `NOT_SLOW`, 25 `WATCHLIST`, 25 `HIDDEN_OPPORTUNITY`, one `SEASONAL_REVIEW`, one `INSUFFICIENT_HISTORY`, and zero confirmed `SLOW_MOVER`. Item 2 is a low-volume, high-margin opportunity; item 8 has concentrated monthly sales; item 9 has insufficient introduction history. The exact fixture tests additionally prove that a persistent declining item becomes `SLOW_MOVER` and the same item can be slow in location A but strong in location B. These fixture outcomes are not claims about real restaurants.

Run from the project root:

```powershell
python -m scripts.refresh_slow_moving_evidence
python -m pytest tests/test_slow_moving.py tests/test_dynamic_app.py tests/test_business_methods.py -q
python tests/browser_phase7_smoke.py
node --check DineiqFrantend/template/assets/js/dineiq-demo.js
```

The browser test runs against a temporary authentication database and local API. It is not deployment or uptime evidence.

Verification: the final focused plus relevant regression suite passed 25 tests with one existing Starlette deprecation warning; the extra implicit regional-scope assertion passed in its focused rerun. Headless Chromium rendered the slow-status menu filter and a slow-moving recommendation, alongside its Phase 6 forecast checks. `node --check`, Python compilation, and `git diff --check` passed. Running the report refresh twice produced the same report SHA-256, so the report update is repeatable.
