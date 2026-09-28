# DineIQ integration status

The previous rapid demo remains as protected compatibility routes, but the main frontend now calls cleaned, Parquet-backed endpoints and authenticates with JWT. Read the root README for run commands, `docs/API.md` for endpoints, and `docs/LIMITATIONS.md` before presenting model results.

Verified locally:

- 959,964 clean completed order lines persisted both in a single Parquet and 20 location partitions, with discount-aware net revenue and contribution. All 150 menu items retain valid historical-price sales.
- 96,010 unique completed orders in the validated sales universe.
- 581 shared unseen location-day cases produced independently by Python and Spark MLlib. Python MAE: 70.48; selected Spark Random Forest MAE: 79.25; fixed 50-unit agreement: 86.23%.
- Three Spark MLlib algorithms were trained and validated; the selected native Spark model could not be saved in this Windows Hadoop environment.
- Clean RFM/KMeans segments cover 48,886 customers, with five profiled clusters and a 0.5280 sampled silhouette score.
- Weekly wastage model uses 6,149 observed chronological holdout weeks. Missing source weeks remain unknown; amount MAE 0.793 is worse than the 0.653 baseline, and high-risk recall is 23.03%. Its alert list remains experimental.
- Price/promotion equal-window economics, a promotion-trap flag, rating anomaly flags, channel/location comparison, churn evidence, and persistent recommendations are exposed through current APIs.
- 300 basket association rules meeting pair count >=100 and lift >=1.05.
- Spark SQL produced 150 item, 20 location, and 480 location-hour rows from partitioned clean Parquet.
- JWT, database roles, regional scoping, audited what-if and CSV/Excel exports, and queued/running/final local jobs.
- Management create/edit routes for locations, categories, items, promotions, inventory, wastage, users, and roles. Validated wastage edits update live aggregates; managed changes do not rewrite historical Parquet or retrain models automatically.
- Automated API and business-method tests and JavaScript syntax checks are run using the commands in README.

Known incomplete work is listed in `docs/LIMITATIONS.md`. The 66-item section-1.6 functional estimate is in `docs/CURRENT_SRS_REAUDIT.md`; it excludes mandatory nonfunctional and submission evidence, so it is not an overall SRS compliance claim.
