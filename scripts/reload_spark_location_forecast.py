"""Load the persisted selected Spark model in a fresh process and check its fixture."""

import json
import math
from pathlib import Path

from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import (DecisionTreeRegressionModel, LinearRegressionModel,
                                   RandomForestRegressionModel)

from spark_jobs.ingest import create_spark


ROOT = Path(__file__).resolve().parents[1]
MODEL_CLASSES = {"LinearRegression": LinearRegressionModel,
                 "DecisionTreeRegressor": DecisionTreeRegressionModel,
                 "RandomForestRegressor": RandomForestRegressionModel}


def reload_and_check(version="spark-location-selected-v4"):
    model_root = ROOT / "Models" / "spark" / "location_forecast" / version
    manifest = json.loads((model_root / "manifest.json").read_text(encoding="utf-8"))
    fixture = json.loads((model_root / "reload_fixture.json").read_text(encoding="utf-8"))
    assert manifest["model_version"] == version
    assert fixture, "Reload fixture is empty"
    features = manifest["features"]
    model_path = ROOT / manifest["model_path"]
    spark = create_spark("DineIQ-Spark-Location-Reload")
    try:
        model = MODEL_CLASSES[manifest["algorithm"]].load(str(model_path))
        records = [{**dict(zip(features, entry["features"])), "fixture_id": index}
                   for index, entry in enumerate(fixture)]
        frame = VectorAssembler(inputCols=features, outputCol="features").transform(
            spark.createDataFrame(records))
        predictions = {row.fixture_id: float(row.prediction)
                       for row in model.transform(frame).select("fixture_id", "prediction").collect()}
        for index, entry in enumerate(fixture):
            assert math.isclose(predictions[index], entry["expected_prediction"],
                                rel_tol=0, abs_tol=1e-6), (index, predictions[index], entry)
        result = {"model_path": str(manifest["model_path"]), "fixtures_checked": len(fixture),
                  "matched": True}
        print(json.dumps(result))
        return result
    finally:
        spark.stop()


if __name__ == "__main__":
    reload_and_check()
