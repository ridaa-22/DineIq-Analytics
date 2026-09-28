# DineIQ mandatory SRS re-audit

Baseline: 28 September 2026, before the follow-up work requested in the latest brief. Source: the complete 52-page `DineIQ Analytics-Data Science Intelligence Arena_SRS.pdf`, especially section 1.6 (pages 28–33), section 1.7 (page 34), and deliverables (pages 38–52). `D` = DONE, `P` = PARTIAL, `M` = MISSING. Optional examples and technologies are excluded. This file is a baseline; later code changes must be rechecked before changing a status.

| FR | Mandatory requirement | Status | Evidence and remaining gap |
| --- | --- | --- | --- |
| 1 | Registration/authentication | D | `fast_apis/services/auth_service.py`: PBKDF2, JWT, login/logout |
| 2 | Role access control | D | FastAPI dependencies; regional scope tests |
| 3 | Location management | P | API create/update; no complete management UI |
| 4 | Menu management | P | SQLite categories/items and edit API; incomplete add/UI |
| 5 | Pricing history | P | Seeded history and price edit insertion; limited UI |
| 6 | Anonymized customer profiles | P | Raw named customers; analytical RFM lacks profile management |
| 7 | Order headers and lines | D | Raw files, validated orders and clean sales Parquet |
| 8 | Promotion management | P | Campaign metadata/edit API; coupons not modeled |
| 9 | Rating management | P | Ratings Parquet linked to order/item; no management API |
| 10 | Inventory management | P | Raw Inventory file; no maintained application workflow |
| 11 | Wastage records | D | Raw and cleaned wastage Parquet with item/location/date/cost/reason |
| 12 | Spark ingestion | D | `spark_jobs/ingest.py` and ingestion tests |
| 13 | Schema and relationship validation | P | Explicit schemas/type checks; full referential validation incomplete |
| 14 | Data-quality analysis | P | `quality_report.json` counts; incomplete condition-level report |
| 15 | Documented cleaning | P | `build_processed.py` persists clean data; per-rule decision log incomplete |
| 16 | Spark SQL | P | `spark_jobs/processed_sql.py` aggregates; required integration joins incomplete |
| 17 | Large-data partitioning | M | No documented partition strategy/output partitioning |
| 18 | Processed Parquet | D | 936,903 clean completed lines in `data/processed/phase1-v1/sales.parquet` |
| 19 | Derived business/ML features | P | Revenue, cost, RFM, lag features; full SRS feature set incomplete |
| 20 | Profitability | D | Discount-aware revenue, cost, contribution, profit % |
| 21 | Menu classes | P | Four classes use only median volume/profit; other mandatory dimensions not used |
| 22 | Peak periods | P | Spark peak-hour CSV and legacy reports; seasonal views not integrated |
| 23 | Customer segmentation | P | Current RFM rules; legacy KMeans uses different raw data |
| 24 | RFM | D | Clean completed sales; unique order frequency; net monetary |
| 25 | Market basket | D | `build_basket_rules.py` from clean completed orders |
| 26 | Support/confidence/lift | D | 288 persisted rules with evidence thresholds |
| 27 | Bundle recommendations | P | Rules exposed; no recommendation handoff to bundles |
| 28 | Future demand forecasting | P | Saved Python one-day location forecast; no broader demand granularity |
| 29 | Forecast evaluation | D | 600 chronological holdout cases, MAE/RMSE and lag-7 baseline |
| 30 | Wastage trends | P | Clean item/location totals; time trends incomplete |
| 31 | Wastage prediction | M | Prior model uses same-period leakage; new app labels unavailable |
| 32 | Price sensitivity | P | 28-day before/after endpoint yields only limited events |
| 33 | Promotion effectiveness | P | Campaign totals; before/during/after and wastage missing |
| 34 | Promotion trap detection | M | No supported sales-up/contribution-down test |
| 35 | Rating analysis | P | Item averages; weak location/performance relationship |
| 36 | Rating anomalies | M | Invalid ratings are cleaned, not behavioral anomaly detection |
| 37 | Sales anomalies | D | Location-day z score and unusual order discount/quantity rules |
| 38 | Location comparison | P | Scoped dashboard and Spark location aggregate; standardized comparison UI limited |
| 39 | Location-specific menu | D | Menu endpoint computes metrics and classes after location scope |
| 40 | Channel analysis | M | Channel filter on orders; no channel comparison intelligence |
| 41 | Churn risk | P | Recency >90-day rule; no declining-pattern model/profile |
| 42 | At least three Spark MLlib algorithms | P | One independent Random Forest trained; no three-way evaluation or saved Spark model |
| 43 | Independent Python ML | P | Saved Python RF and legacy models, but mixed data provenance |
| 44 | Dual prediction comparison | D | 600 same underlying unseen location-day cases |
| 45 | Agreement/disagreement | D | Fixed 50-unit threshold, difference and reason per case |
| 46 | Model evaluation | P | Forecast metrics; other model evidence not yet coherent |
| 47 | Recommendation engine | P | Evidence rules exist; results not persisted and categories incomplete |
| 48 | Menu optimization actions | P | Visibility, repricing, wastage; no full redesign/removal/bundle actions |
| 49 | Inventory recommendations | M | No supported forecast/wastage inventory planning rule |
| 50 | Customer targeting | M | Segments not mapped to strategies |
| 51 | What-if | P | Price, discount, user demand estimates; inventory delta not calculated |
| 52 | Executive dashboard | P | Real core KPIs; forecast, anomalies and recommendations not integrated there |
| 53 | Menu dashboard | P | Real table but limited factors/filters |
| 54 | Customer dashboard | P | RFM visible; validated KMeans absent |
| 55 | Wastage dashboard | P | Totals/item/location visible; trend/risk absent |
| 56 | Forecast dashboard | D | Historical actual/prediction/error plus next-day estimate |
| 57 | Dual pipeline dashboard | D | Both predictions, metrics, agreement and versions |
| 58 | Search/filtering | P | Location/date/class/segment/channel/status supported across selected views; SRS set incomplete |
| 59 | Downloadable reports | D | Authenticated report route |
| 60 | Data export | D | Current cleaned CSV/Excel export, scoped and audited |
| 61 | Database storage | P | SQLite users/metadata/jobs/versions/logs; analytical results/recommendations incompletely persisted |
| 62 | Model versions | D | Version/dataset in predictions and model table |
| 63 | Audit trail | P | Login/logout, what-if, export, admin, prediction; processing lifecycle incomplete |
| 64 | Error handling | P | API HTTP errors and UI messages; Spark/data failures not unified |
| 65 | Spark job monitoring | P | Stored completed rows only; no live status transitions |
| 66 | Responsive interface | P | Template has responsive CSS; no supported-browser evidence |

Baseline functional score: **20 D, 39 P, 7 M = (20 + 0.5×39)/66 = 59.8%**. This is a functional-only estimate, not whole-SRS compliance. Needs-interpretation items in the nonfunctional wording are excluded until clarified.

Mandatory nonfunctional and submission gaps are material: the five-second NFR refers to “claim details” (an SRS wording conflict); five-million-line scalability, 99% uptime, and browser usability lack benchmark evidence. The SRS also requires three Spark algorithms and a saved model, extensive test categories, full data dictionary/report/installation evidence, public repository and contribution history, a demo video, published 2,000-word blog, presentation, and human AI review declaration. Local absence of a public URL, video, or blog is **not verifiable as submitted** from this workspace. Their completion cannot be assumed from the functional score.

Fastest technical path: multifactor menu classes; one authoritative clean RFM/KMeans pipeline; leakage-free wastage risk; three Spark algorithms and model persistence; price/promotion windows; management UI/data workflows; real job states; focused contradictory-case tests; complete documentation and submission evidence. Do not create supervised menu labels from a heuristic rule.

## Follow-up verification: 28 September 2026

The table above is retained as the **pre-work baseline**. After implementing and testing the follow-up work, the functional statuses below replace its score. `D` = DONE, `P` = PARTIAL, `M` = MISSING. They score only the 66 explicit functional requirements in SRS section 1.6; they are **not** an overall SRS compliance score.

| IDs | Current statuses in ID order |
| --- | --- |
| 1–11 | D D D D D P D P P D D |
| 12–22 | D P P P P D D P D D P |
| 23–33 | D D D D D P D P P P D |
| 34–44 | D P D D D D D D D D D |
| 45–55 | D D D P P P P P P D D |
| 56–66 | D D D D D P D D P D P |

Count: **43 DONE, 23 PARTIAL, 0 MISSING**. Functional-only weighted estimate: `(43 + 0.5 × 23) / 66 = 82.6%`. This is an estimate, not a claim of full compliance. The 23 partial items remain gaps, and mandatory NFRs, test categories, saved Spark model, and final submission deliverables are outside this denominator.

Changed-status evidence, compared with the baseline:

- FR3–5 and FR10: `fast_apis/routes/management.py` and the frontend management view now create/edit locations, categories, items, effective-price history, promotion metadata, and inventory period records; role restrictions and audit entries are exercised in `tests/test_dynamic_app.py`. FR8 remains partial because coupons and historical analytics refresh are absent.
- FR17–18: `Python_Pipeline/build_processed.py` writes 959,964 clean lines both as one Parquet and 20 `Location_ID` Parquet partitions; `spark_jobs/processed_sql.py` reads the partitioned files and produces 150 item, 20 location, and 480 location-hour outputs. Partition metadata are in `partition_strategy.json`, and a test checks the partition and single-file row totals.
- FR13–15 remain partial: `quality_report.json` now records raw duplicates, missing values, invalid numeric values, referential checks, and counts after cleaning, plus rules for each output. The pipeline still lacks per-record quarantine/decision lineage and complete cross-entity checks such as rating purchase-pair and effective-price-at-order validation. Its counts can overlap across conditions.
- FR21 and FR23: all 150 menu items now reach the multifactor descriptive classifier. Five invalid raw `Base_Price` values remain flagged, while valid historical effective transaction prices preserve their clean sales. `Python_Pipeline/train_customer_segments.py` trains on clean Parquet, selects k by sampled silhouette, profiles clusters before naming, and saves `customer_rfm_kmeans.joblib` plus segment output. The former 152-day "Engaged" profile is now "Cooling" in v4.
- FR27 and FR47: `/api/analytics/recommendations` derives bundle and other actions from support/confidence/lift, item metrics, segment profiles, campaign windows, and wastage estimates. Evidence and priority are persisted in SQLite for global actions. FR48–50 remain partial because suitable actions and inventory/customer strategies do not yet cover all mandatory business use cases robustly.
- FR31: `Python_Pipeline/train_wastage_forecast.py` uses prior-week features and a chronological 6,149-case observed-week holdout. Missing records remain unknown. Risk precision is 49.28%, recall 23.03%; amount MAE 0.793 is worse than baseline 0.653. Operational risk detection remains partial despite a saved model and endpoint.
- FR33–34: `Python_Pipeline/business_windows.py` and the promotion endpoint compare equal before/during/after campaign windows; campaign 1 yields a sales-up/contribution-down trap. FR32 remains partial because the generated data contain one genuine price change.
- FR36, FR38, FR40–41: the live API now exposes rating-burst flags, standardized location KPIs, channel comparisons, and recency/decline churn flags. Their UI views use real API results.
- FR42: `spark_jobs/train_location_forecast.py` genuinely fits and validates Linear Regression, Decision Tree, and Random Forest; see `Models/integrated/spark_selection_metrics.json`. This functional requirement is done. The separate **saved Spark model deliverable is incomplete** because native persistence failed here.
- FR43 and FR46: independent saved Python forecast, clean RFM/KMeans, and experimental wastage model have train/holdout metrics. FR44–45 remain done using 581 unseen common cases, model versions, differences, and a fixed agreement threshold.
- FR54–55 and FR58: customer profiles, clean wastage record fields, and multiple location/category/class/segment/date/channel/status filters are in `DineiqFrantend/template/assets/js/dineiq-demo.js`. FR52–53 remain partial due incomplete executive and menu experience.
- FR63 and FR65: `fast_apis/services/job_service.py` records queued/running/final job states, output/error tails and audit events; the job view polls status. Spark model-save failure produces `COMPLETED_WITH_WARNINGS` rather than an unqualified completion. FR64 remains partial because error presentation across all failure modes is unverified.

Remaining cross-cutting blockers: managed wastage updates live aggregates but not the versioned model-training data, while other operational changes also lack a refresh path; the Spark model is not saved; the wastage classifier misses most positive-risk weeks and its amount estimate loses to baseline; forecast quality, scalability, availability, security, browser, and final-submission evidence are not fully verified. These prevent an overall SRS-compliant verdict.
