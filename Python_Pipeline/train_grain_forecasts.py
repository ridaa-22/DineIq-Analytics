"""Train one shared recursive forecasting method at three demand grains."""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from Python_Pipeline.forecast_features import (FEATURES, GRAINS, HORIZONS, ROOT,
                                               daily_series, feature_frame,
                                               histories_before, recursive_forecast)


OUT = ROOT / "Models" / "integrated"
VERSION = "python-multigrain-rf-v1"
DATASET_VERSION = "phase1-v1-clean-v3"


def score_window(model, daily, origin, horizon):
    predicted = recursive_forecast(model, histories_before(daily, origin),
                                   pd.Timestamp(origin) + pd.Timedelta(days=1), horizon)
    actual = daily.rename(columns={"Demand": "Actual"})
    return predicted.merge(actual, on=["Date", "Entity_ID"], how="inner", validate="one_to_one")


def metrics_by_horizon(rows):
    scores = {}
    for horizon in HORIZONS:
        cases = rows[rows.Lead.eq(horizon)]
        scores[str(horizon)] = {"cases": len(cases),
                                "mae": float(np.mean(abs(cases.Actual - cases.Prediction))) if len(cases) else None,
                                "baseline_mae": float(np.mean(abs(cases.Actual - cases.Baseline))) if len(cases) else None}
    return scores


def train():
    OUT.mkdir(parents=True, exist_ok=True)
    all_test = []
    summary = {"model_version": VERSION, "dataset_version": DATASET_VERSION,
               "features": FEATURES, "horizons": HORIZONS, "grains": {}}
    for grain in GRAINS:
        daily = daily_series(grain)
        featured = feature_frame(daily)
        last = daily.Date.max()
        validation_end = last - pd.Timedelta(days=30)
        training_end = validation_end - pd.Timedelta(days=30)
        early = featured[featured.Date.le(training_end)]
        full = featured[featured.Date.le(validation_end)]
        if early.empty or full.empty:
            raise ValueError(f"Insufficient chronological training data for {grain}")
        def estimator():
            return RandomForestRegressor(n_estimators=40, min_samples_leaf=3,
                                         random_state=42, n_jobs=-1)
        validation_model = estimator().fit(early[FEATURES], early.Demand)
        validation = score_window(validation_model, daily, training_end, 30)
        model = estimator().fit(full[FEATURES], full.Demand)
        test = score_window(model, daily, validation_end, 30)
        test["Grain"] = grain.upper()
        test["Model_Version"] = VERSION
        test["Dataset_Version"] = DATASET_VERSION
        all_test.append(test)
        artifact = {"model": model, "features": FEATURES, "grain": grain,
                    "version": VERSION, "dataset_version": DATASET_VERSION,
                    "last_date": str(last.date()),
                    "last_history": {key: value[-7:] for key, value in histories_before(daily, last).items()}}
        joblib.dump(artifact, OUT / f"multigrain_{grain}.joblib")
        summary["grains"][grain] = {
            "training_range": {"start": str(early.Date.min().date()), "end": str(training_end.date())},
            "validation_range": {"start": str((training_end + pd.Timedelta(days=1)).date()),
                                 "end": str(validation_end.date())},
            "test_range": {"start": str((validation_end + pd.Timedelta(days=1)).date()),
                           "end": str(last.date())},
            "validation": metrics_by_horizon(validation), "test": metrics_by_horizon(test)}
    pd.concat(all_test, ignore_index=True).to_parquet(OUT / "multigrain_holdout.parquet", index=False)
    (OUT / "multigrain_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    train()
