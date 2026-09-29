"""Recompute unchanged model versus seasonal/last-observed baselines on saved holdouts."""

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "Models" / "integrated"


def mae(actual, predicted):
    return float((actual.astype(float) - predicted.astype(float)).abs().mean())


def main():
    python = pd.read_parquet(ART / "python_holdout.parquet")
    spark = pd.read_csv(ART / "spark_holdout.csv")
    daily = pd.read_parquet(ROOT / "data/processed/phase1-v1/location_daily.parquet")
    daily["Date"] = pd.to_datetime(daily.Date)
    daily = daily.sort_values(["Location_ID", "Date"])
    daily["Baseline"] = daily.groupby("Location_ID").Demand.shift(7)
    spark["Date"] = pd.to_datetime(spark.Date)
    spark = spark.merge(daily[["Date", "Location_ID", "Baseline"]],
        on=["Date", "Location_ID"], how="left", validate="one_to_one")
    if spark.Baseline.isna().any() or len(spark) != len(python):
        raise AssertionError("Spark baseline or holdout alignment is incomplete")
    waste = pd.read_parquet(ART / "wastage_holdout.parquet")
    if waste[["Wasted", "Predicted_Wastage", "Baseline"]].isna().any().any():
        raise AssertionError("Observed wastage holdout contains missing evaluation values")
    result = {
        "python_location": {"cases": len(python), "model_mae": mae(python.Actual, python.Python_Prediction),
            "baseline_mae": mae(python.Actual, python.Baseline), "baseline": "observed lag 7"},
        "spark_location": {"cases": len(spark), "model_mae": mae(spark.Actual, spark.Spark_Prediction),
            "baseline_mae": mae(spark.Actual, spark.Baseline), "baseline": "observed lag 7"},
        "wastage_amount": {"cases": len(waste), "model_mae": mae(waste.Wasted, waste.Predicted_Wastage),
            "baseline_mae": mae(waste.Wasted, waste.Baseline), "baseline": "last observed wastage"},
    }
    target = ROOT / "reports" / "nfr_baselines.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
