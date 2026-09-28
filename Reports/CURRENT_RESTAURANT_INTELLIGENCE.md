# Current restaurant intelligence report

Data: synthetic `phase1-v1`, cleaned `phase1-v1-clean-v3`. Generated outputs are observational, not a production restaurant recommendation. Current APIs are the reproducible source for scoped values; legacy CSV reports in this folder may use an older pipeline.

## Evidence and decisions

| Area | Current finding | Source and limit |
| --- | --- | --- |
| Clean sales | 959,964 completed order lines from 96,010 orders, across all 150 menu items | `data/processed/phase1-v1/quality_report.json`; valid historical prices retain the five invalid-base-price items |
| Menu | Four descriptive classes use volume, contribution, ratings, repeats, wastage, promotion dependency, trend, and history | `Python_Pipeline/menu_scoring.py`; class labels are rules, not ground truth |
| Customer | 48,886 clean-RFM customers; KMeans selected five clusters with sampled silhouette 0.5280 | `Models/integrated/customer_segment_metrics.json`; cluster names derive from profiles |
| Basket | 300 association rules from clean completed baskets; support, confidence, lift, and pair count | `data/processed/phase1-v1/basket_rules.csv`; no causal bundle lift measured |
| Demand | 581 common unseen location-day cases; Python MAE 70.48, Spark MAE 79.25, 86.23% prediction agreement within 50 units | `Models/integrated/comparison_metrics.json`; one-step-ahead backtest |
| Wastage | 6,149 observed chronological weekly holdout cases; amount MAE 0.793 versus last-observed baseline 0.653; high-risk precision 49.28%, recall 23.03% | `Models/integrated/wastage_metrics.json`; unobserved source weeks are unknown, not zero |
| Pricing | Item 6 is the only genuine historical list-price change in the current generated history; observed price rose about 40% and equal-window demand fell about 89.9% | `/api/analytics/pricing?item_id=6`; confounded association, not elasticity |
| Promotions | Before/during/after windows include demand, net revenue, contribution, customers, repeat customers, AOV, and wastage; campaign 1 triggers a sales-up/contribution-down trap | `/api/analytics/promotions`; windows are observational |
| Anomalies | Location-day sales z-score flags, unusual transactions, and rating-burst flags are exposed | `/api/analytics/anomalies`; threshold detection, not a learned anomaly model |
| Actions | Menu, pricing, wastage, bundle, inventory, customer targeting, and promotion recommendations carry supporting metrics and priority | `/api/analytics/recommendations`; inventory risk depends on low-recall wastage model |

## Immediate decision constraints

Review item 6's price result with promotion and seasonality context before making a pricing change. Investigate campaign 1's falling contribution alongside its sales increase. Treat high-risk wastage results as prompts for manual review because low recall makes the absence of a flag weak evidence. Do not treat descriptive menu groups or KMeans segment names as verified causal outcomes. Managed SQLite edits do not update this versioned historical dataset automatically.
