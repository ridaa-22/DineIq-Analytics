"""Independent chronological Python forecast on processed location-day demand."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "phase1-v1"
ARTIFACTS = ROOT / "Models" / "integrated"
FEATURES = ["Location_ID", "day_of_week", "month", "lag_1", "lag_7", "rolling_7"]


def feature_frame():
    frame = pd.read_parquet(PROCESSED / "location_daily.parquet")
    frame["Date"] = pd.to_datetime(frame.Date)
    frame = frame.sort_values(["Location_ID", "Date"])
    grouped = frame.groupby("Location_ID").Demand
    frame["lag_1"] = grouped.shift(1)
    frame["lag_7"] = grouped.shift(7)
    frame["rolling_7"] = grouped.transform(lambda x: x.shift(1).rolling(7).mean())
    frame["day_of_week"] = frame.Date.dt.dayofweek
    frame["month"] = frame.Date.dt.month
    return frame.dropna(subset=FEATURES).copy()


def train():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    frame = feature_frame()
    cutoff = frame.Date.max() - pd.Timedelta(days=30)
    train_set, test_set = frame[frame.Date.le(cutoff)], frame[frame.Date.gt(cutoff)].copy()
    model = RandomForestRegressor(n_estimators=80, min_samples_leaf=3, random_state=42, n_jobs=-1)
    model.fit(train_set[FEATURES], train_set.Demand)
    test_set["Python_Prediction"] = np.maximum(0, model.predict(test_set[FEATURES]))
    test_set["Baseline"] = test_set.lag_7
    test_set["Case_ID"] = test_set.Date.dt.strftime("%Y-%m-%d") + ":" + test_set.Location_ID.astype(str)
    test_set = test_set.rename(columns={"Demand": "Actual"})
    test_set["Python_Model_Version"] = "python-location-rf-v3"
    test_set["Dataset_Version"] = "phase1-v1-clean-v3"
    path = ARTIFACTS / "python_forecast.joblib"
    joblib.dump({"model": model, "features": FEATURES, "version": "python-location-rf-v3",
                 "dataset_version": "phase1-v1-clean-v3"}, path)
    test_set.to_parquet(ARTIFACTS / "python_holdout.parquet", index=False)
    metrics = {"model": "RandomForestRegressor", "version": "python-location-rf-v3",
               "dataset_version": "phase1-v1-clean-v3", "cutoff": str(cutoff.date()),
               "holdout_cases": len(test_set), "mae": mean_absolute_error(test_set.Actual, test_set.Python_Prediction),
               "rmse": mean_squared_error(test_set.Actual, test_set.Python_Prediction) ** 0.5,
               "baseline_mae": mean_absolute_error(test_set.Actual, test_set.Baseline)}
    (ARTIFACTS / "python_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    train()
