"""Compare two independently trained models on identical unseen cases."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Models" / "integrated"
TOLERANCE_UNITS = 50.0


def compare():
    python = pd.read_parquet(OUT / "python_holdout.parquet")
    spark = pd.read_csv(OUT / "spark_holdout.csv")
    columns = ["Case_ID", "Date", "Location_ID", "Actual", "Python_Prediction", "Python_Model_Version", "Dataset_Version"]
    merged = python[columns].merge(spark[["Case_ID", "Actual", "Spark_Prediction", "Spark_Model_Version", "Dataset_Version"]],
                                    on="Case_ID", how="inner", suffixes=("", "_Spark"), validate="one_to_one")
    if len(merged) < 100 or len(merged) != len(python) or len(merged) != len(spark):
        raise ValueError("Forecast holdouts differ or fewer than 100 cases")
    if not (merged.Actual == merged.Actual_Spark).all() or not (merged.Dataset_Version == merged.Dataset_Version_Spark).all():
        raise ValueError("The two pipelines do not share equivalent actual values and dataset version")
    merged["Difference"] = (merged.Spark_Prediction - merged.Python_Prediction).abs()
    merged["Spark_Error"] = (merged.Spark_Prediction - merged.Actual).abs()
    merged["Python_Error"] = (merged.Python_Prediction - merged.Actual).abs()
    merged["Match_Status"] = merged.Difference.le(TOLERANCE_UNITS).map({True: "Match", False: "Mismatch"})
    merged["Disagreement_Reason"] = merged.Match_Status.map({"Match": "Within fixed 50-unit tolerance",
                                                               "Mismatch": "Predictions differ by more than 50 units"})
    merged = merged.drop(columns=["Actual_Spark", "Dataset_Version_Spark"])
    merged.to_csv(OUT / "dual_pipeline_comparison.csv", index=False)
    summary = {"case_count": len(merged), "spark_mae": merged.Spark_Error.mean(),
               "python_mae": merged.Python_Error.mean(), "average_difference": merged.Difference.mean(),
               "agreement_percentage": 100 * merged.Match_Status.eq("Match").mean(),
               "tolerance_units": TOLERANCE_UNITS, "dataset_version": "phase1-v1-clean-v3"}
    (OUT / "comparison_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    compare()
