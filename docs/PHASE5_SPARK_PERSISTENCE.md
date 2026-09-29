# Phase 5: selected Spark model persistence

The native Windows tiny-model probe reproduced the audit failure: Spark ML training completed, then `save()` raised `FileNotFoundException: HADOOP_HOME and hadoop.home.dir are unset` through Hadoop `RawLocalFileSystem.setPermission`.

```powershell
python -m scripts.spark_persistence_probe train Models/spark_probe
```

The reproducible execution environment is `docker/spark/Dockerfile`, based on Apache Spark 4.0.2 with NumPy 1.26.4. It uses the existing project dataset mounted at `/workspace`; no raw data or forecasting algorithm was changed.

Run from the repository root in PowerShell:

```powershell
docker build -t dineiq-spark:4.0.2 -f docker/spark/Dockerfile .
docker run --rm -u 0 -v "D:\SAAS\DineIQ\DineIq-Analytics:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m scripts.spark_persistence_probe train Models/spark_probe_linux
docker run --rm -u 0 -v "D:\SAAS\DineIQ\DineIq-Analytics:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m scripts.spark_persistence_probe load Models/spark_probe_linux
docker run --rm -u 0 -v "D:\SAAS\DineIQ\DineIq-Analytics:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m spark_jobs.train_location_forecast
docker run --rm -u 0 -v "D:\SAAS\DineIQ\DineIq-Analytics:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m scripts.reload_spark_location_forecast
docker run --rm -u 0 -v "D:\SAAS\DineIQ\DineIq-Analytics:/workspace" --entrypoint python3 dineiq-spark:4.0.2 -m unittest discover -s tests -p test_spark_model_persistence.py -v
```

The train and load commands are distinct Docker processes. The selected model is at `Models/spark/location_forecast/spark-location-selected-v4/model/`; its sibling `manifest.json` records model and dataset versions, algorithm, ordered features, chronological split ranges, validation/test MAE, holdout count, and UTC creation time. `reload_fixture.json` contains three held-out feature vectors and expected raw predictions.

Evidence from this run: the tiny model saved, then reloaded with prediction `5.0` matching its fixture. The selected RandomForestRegressor saved with `save_error: null`, 581 holdout cases, validation MAE `42.50720070133772`, and test MAE `79.24595661593085`. A fresh process loaded it and matched all three fixture predictions at absolute tolerance `1e-6`. The holdout CSV SHA-256 remained `006BCBB365BF0AB86C32E67DCAF021C6746BD7E11B4DAB7FB3DB328A11CB6AA1` before and after retraining.

The focused `test_spark_model_persistence.py` integration test passed (1 test). Existing `test_business_methods.py` and `test_dynamic_app.py` regressions passed (21 tests, one Starlette deprecation warning). `python -m py_compile` passed for the changed Python modules. The existing 581-row holdout and comparison artifact were retained.

This backtest uses observed lag values during the holdout period. Live API inference and native Windows saving remain separate limitations; see `docs/LIMITATIONS.md`.
