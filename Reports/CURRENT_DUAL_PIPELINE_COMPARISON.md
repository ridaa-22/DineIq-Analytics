# Independent location-demand pipeline comparison

Dataset: clean `data/processed/phase1-v1/location_daily.parquet`, version `phase1-v1-clean-v3`. Both pipelines independently create prior-demand lag features and train on the shared underlying location-day series. Neither pipeline imports the other's predictions. The chronological test cutoff is 2025-12-02; 581 later location-day cases have matching case IDs and actuals.

| Pipeline | Model selection | Holdout MAE | Saved model |
| --- | --- | ---: | --- |
| Python/scikit-learn | Random Forest with saved feature metadata | 70.4840 | `Models/integrated/python_forecast.joblib` |
| Spark MLlib | Linear Regression (validation MAE 45.64), Decision Tree (42.65), Random Forest (42.51); selected Random Forest | 79.2460 | **No**: native save failed on this Windows Hadoop environment |

Agreement is **86.23%** under a fixed absolute difference tolerance of 50 demand units; average absolute model difference is **31.56** units. A match is agreement between model predictions, not proof either is correct. Both models use previous observed days in the test period for one-step-ahead lags. This is not a recursive multi-day forecast.

Machine-readable evidence: `Models/integrated/python_metrics.json`, `spark_selection_metrics.json`, `comparison_metrics.json`, `spark_holdout.csv`, and `dual_pipeline_comparison.csv`. `Python_Pipeline.compare_location_forecasts` verifies identical case IDs and actuals before writing the joined result. The Spark model persistence requirement remains incomplete until a native model directory can be saved and loaded.
