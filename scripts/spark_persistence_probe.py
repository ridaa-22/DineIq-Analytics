"""Tiny Spark save/load probe, independent of the DineIQ training pipeline."""

import argparse
import json
from pathlib import Path

from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import DecisionTreeRegressor, DecisionTreeRegressionModel
from pyspark.sql import functions as F

from spark_jobs.ingest import create_spark


def probe(mode, root):
    root = Path(root)
    model_path = root / "tiny_model"
    fixture_path = root / "expected.json"
    spark = create_spark("DineIQ-Tiny-Spark-Persistence-Probe")
    try:
        data = spark.range(8).select(F.col("id").cast("double").alias("x"),
                                     (F.col("id") * 2).cast("double").alias("y"))
        features = VectorAssembler(inputCols=["x"], outputCol="features").transform(data)
        if mode == "train":
            model = DecisionTreeRegressor(featuresCol="features", labelCol="y", maxDepth=2).fit(features)
            model.write().overwrite().save(str(model_path))
            expected = float(model.transform(features.filter(F.col("x") == 3)).first().prediction)
            fixture_path.write_text(json.dumps({"x": 3.0, "expected": expected}), encoding="utf-8")
            print(json.dumps({"saved": str(model_path), "expected": expected}))
        else:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            model = DecisionTreeRegressionModel.load(str(model_path))
            actual = float(model.transform(features.filter(F.col("x") == fixture["x"])).first().prediction)
            if abs(actual - fixture["expected"]) > 1e-9:
                raise AssertionError(f"Round trip changed prediction: {actual} vs {fixture['expected']}")
            print(json.dumps({"loaded": str(model_path), "prediction": actual, "matched": True}))
    finally:
        spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["train", "load"])
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    probe(args.mode, args.root)
