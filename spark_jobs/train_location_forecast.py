"""Independent Spark MLlib forecast on the shared processed location-day data."""

import json
import csv
from datetime import datetime, timezone
from pathlib import Path

from pyspark.ml.feature import VectorAssembler
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.regression import DecisionTreeRegressor, LinearRegression, RandomForestRegressor
from pyspark.sql import SparkSession, functions as F, Window

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Models" / "integrated"
FEATURES = ["Location_ID", "day_of_week", "month", "lag_1", "lag_7", "rolling_7"]
MODEL_VERSION = "spark-location-selected-v4"
DATASET_VERSION = "phase1-v1-clean-v3"
MODEL_ROOT = ROOT / "Models" / "spark" / "location_forecast" / MODEL_VERSION


def train():
    OUT.mkdir(parents=True, exist_ok=True)
    spark = SparkSession.builder.appName("DineIQ Independent Location Forecast").master("local[2]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        frame = spark.read.parquet(str(ROOT / "data" / "processed" / "phase1-v1" / "location_daily.parquet"))
        frame = frame.withColumn("date_value", F.to_date("Date"))
        order = Window.partitionBy("Location_ID").orderBy("date_value")
        rolling = order.rowsBetween(-7, -1)
        frame = (frame.withColumn("lag_1", F.lag("Demand", 1).over(order))
                 .withColumn("lag_7", F.lag("Demand", 7).over(order))
                 .withColumn("rolling_7", F.avg("Demand").over(rolling))
                 .withColumn("day_of_week", (F.dayofweek("date_value") + 5) % 7)
                 .withColumn("month", F.month("date_value")))
        frame = frame.dropna(subset=FEATURES)
        cutoff = frame.agg(F.date_sub(F.max("date_value"), 30)).first()[0]
        vector = VectorAssembler(inputCols=FEATURES, outputCol="features")
        validation_start = frame.agg(F.date_sub(F.max("date_value"), 60)).first()[0]
        training = vector.transform(frame.filter(F.col("date_value") <= F.lit(validation_start)))
        validation = vector.transform(frame.filter((F.col("date_value") > F.lit(validation_start)) &
                                                    (F.col("date_value") <= F.lit(cutoff))))
        training_full = vector.transform(frame.filter(F.col("date_value") <= F.lit(cutoff)))
        testing = vector.transform(frame.filter(F.col("date_value") > F.lit(cutoff)))
        algorithms = {
            "LinearRegression": LinearRegression(featuresCol="features", labelCol="Demand", regParam=0.1,
                                                  elasticNetParam=0),
            "DecisionTreeRegressor": DecisionTreeRegressor(featuresCol="features", labelCol="Demand",
                                                             maxDepth=8, minInstancesPerNode=3, seed=42),
            "RandomForestRegressor": RandomForestRegressor(featuresCol="features", labelCol="Demand", numTrees=50,
                                                             maxDepth=10, minInstancesPerNode=3, seed=42),
        }
        mae = RegressionEvaluator(labelCol="Demand", predictionCol="prediction", metricName="mae")
        candidates = []
        for name, algorithm in algorithms.items():
            fitted = algorithm.fit(training)
            score = float(mae.evaluate(fitted.transform(validation)))
            candidates.append({"algorithm": name, "validation_mae": score,
                               "hyperparameters": {key.name: str(value) for key, value in algorithm.extractParamMap().items()}})
        selected = min(candidates, key=lambda result: result["validation_mae"])["algorithm"]
        model = algorithms[selected].fit(training_full)
        saved_path = MODEL_ROOT / "model"
        save_error = None
        try:
            model.write().overwrite().save(str(saved_path))
        except Exception as exc:
            save_error = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        predicted = (model.transform(testing)
                     .select(F.concat_ws(":", F.col("Date"), F.col("Location_ID")).alias("Case_ID"),
                             F.col("Date"), F.col("Location_ID"), F.col("Demand").alias("Actual"),
                             F.greatest(F.col("prediction"), F.lit(0.0)).alias("Spark_Prediction"),
                             F.lit(MODEL_VERSION).alias("Spark_Model_Version"),
                             F.lit(DATASET_VERSION).alias("Dataset_Version")))
        rows = predicted.collect()
        with (OUT / "spark_holdout.csv").open("w", newline="", encoding="utf-8") as destination:
            writer = csv.DictWriter(destination, fieldnames=predicted.columns)
            writer.writeheader()
            writer.writerows(row.asDict() for row in rows)
        metrics = {"version": MODEL_VERSION, "dataset_version": DATASET_VERSION,
                   "validation_start": str(validation_start), "test_cutoff": str(cutoff),
                   "holdout_cases": len(rows), "candidates": candidates, "selected_algorithm": selected,
                   "test_mae": float(mae.evaluate(model.transform(testing))),
                   "model_path": str(saved_path.relative_to(ROOT)) if save_error is None else None,
                   "save_error": save_error}
        if save_error is None:
            ranges = {}
            for name, dataset in (("training", training), ("validation", validation), ("test", testing)):
                bounds = dataset.agg(F.min("date_value").alias("start"),
                                     F.max("date_value").alias("end")).first()
                ranges[name] = {"start": str(bounds.start), "end": str(bounds.end)}
            fixture_rows = (model.transform(testing).orderBy("date_value", "Location_ID")
                            .select(*FEATURES, "prediction").limit(3).collect())
            fixture = [{"features": [float(row[name]) for name in FEATURES],
                        "expected_prediction": float(row.prediction)} for row in fixture_rows]
            (MODEL_ROOT / "reload_fixture.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
            manifest = {"model_name": "location_forecast", "model_version": MODEL_VERSION,
                        "dataset_version": DATASET_VERSION, "algorithm": selected,
                        "features": FEATURES, "model_path": str(saved_path.relative_to(ROOT)),
                        "training_range": ranges["training"], "validation_range": ranges["validation"],
                        "test_range": ranges["test"],
                        "metrics": {"validation_mae": next(c["validation_mae"] for c in candidates
                                                        if c["algorithm"] == selected),
                                    "test_mae": metrics["test_mae"], "holdout_cases": len(rows)},
                        "created_at": datetime.now(timezone.utc).isoformat()}
            (MODEL_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (OUT / "spark_selection_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(json.dumps({key: metrics[key] for key in ("holdout_cases", "selected_algorithm", "test_mae", "model_path", "save_error")}, indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    train()
