"""Next-week wastage forecast using only past-known weekly features."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error, mean_squared_error,
                             precision_score, recall_score)

from Python_Pipeline.wastage_features import (FEATURES, MISSING_WEEK_POLICY,
    PREPROCESSING_VERSION, build_next_week_features, build_wastage_features)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "phase1-v1"
OUT = ROOT / "Models" / "integrated"
VERSION = "weekly-wastage-hgb-v6"


def weekly_frame():
    waste = pd.read_parquet(DATA / "wastage.parquet")
    sales = pd.read_parquet(DATA / "sales.parquet", columns=["Item_ID", "Location_ID", "Order_DateTime", "Quantity"])
    waste["Week"] = waste.Wastage_Date.dt.to_period("W-SUN").dt.start_time
    sales["Week"] = sales.Order_DateTime.dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    waste = waste.groupby(["Item_ID", "Location_ID", "Week"], as_index=False).agg(
        Wasted=("Quantity_Wasted", "sum"), Prepared=("Prepared_Quantity", "sum"))
    demand = sales.groupby(["Item_ID", "Location_ID", "Week"], as_index=False).Quantity.sum().rename(
        columns={"Quantity": "Demand"})
    items = sorted(sales.Item_ID.unique())
    locations = sorted(sales.Location_ID.unique())
    weeks = pd.date_range(min(waste.Week.min(), demand.Week.min()), max(waste.Week.max(), demand.Week.max()), freq="W-MON")
    grid = pd.MultiIndex.from_product([items, locations, weeks], names=["Item_ID", "Location_ID", "Week"]).to_frame(index=False)
    data = grid.merge(waste, on=["Item_ID", "Location_ID", "Week"], how="left").merge(
        demand, on=["Item_ID", "Location_ID", "Week"], how="left")
    return build_wastage_features(data)


def train():
    OUT.mkdir(parents=True, exist_ok=True)
    data = weekly_frame()
    cutoff = data.Week.max() - pd.Timedelta(weeks=8)
    # The source is a sample of observed item/location/days. An absent record
    # is unknown, not a measured zero. Train and score observed weeks only.
    observed = data[data.Wasted.notna()].copy()
    holdout = observed[observed.Week.gt(cutoff)].copy()
    validation_start = cutoff - pd.Timedelta(weeks=8)
    training = observed[observed.Week.le(validation_start)].copy()
    validation = observed[observed.Week.gt(validation_start) & observed.Week.le(cutoff)].copy()
    model = HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=25, l2_regularization=1,
                                          random_state=42).fit(training[FEATURES], training.Wasted)
    validation["Predicted_Wastage"] = np.maximum(0, model.predict(validation[FEATURES]))
    validation["Baseline"] = validation.last_observed_waste.fillna(0)
    holdout["Predicted_Wastage"] = np.maximum(0, model.predict(holdout[FEATURES]))
    holdout["Baseline"] = holdout.last_observed_waste.fillna(0)
    high_cut = float(training.loc[training.Wasted.gt(0), "Wasted"].quantile(.75))
    risk_model = HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=25,
        l2_regularization=1, random_state=42).fit(training[FEATURES], training.Wasted.gt(high_cut))
    validation_probabilities = risk_model.predict_proba(validation[FEATURES])[:, 1]
    thresholds = np.arange(.1, .91, .05)
    threshold = float(max(thresholds, key=lambda value: f1_score(
        validation.Wasted.gt(high_cut), validation_probabilities >= value,
        zero_division=0)))
    validation_f1 = float(f1_score(validation.Wasted.gt(high_cut),
                                   validation_probabilities >= threshold, zero_division=0))
    holdout["Actual_High_Risk"] = holdout.Wasted.gt(high_cut)
    holdout["Risk_Probability"] = risk_model.predict_proba(holdout[FEATURES])[:, 1]
    holdout["Predicted_High_Risk"] = holdout.Risk_Probability.ge(threshold)
    holdout["Case_ID"] = holdout.Week.dt.strftime("%Y-%m-%d") + ":" + holdout.Item_ID.astype(str) + ":" + holdout.Location_ID.astype(str)
    holdout.to_parquet(OUT / "wastage_holdout.parquet", index=False)
    latest = build_next_week_features(data)
    latest["Expected_Wastage"] = np.maximum(0, model.predict(latest[FEATURES]))
    latest["Risk_Probability"] = risk_model.predict_proba(latest[FEATURES])[:, 1]
    latest["Risk"] = pd.cut(latest.Expected_Wastage, [-1, high_cut * .5, high_cut, float("inf")],
                            labels=["LOW", "MEDIUM", "HIGH"]).astype(str)
    latest.loc[latest.Risk_Probability.ge(threshold), "Risk"] = "HIGH"
    latest.loc[latest.Risk_Probability.lt(threshold) & latest.Risk.eq("HIGH"), "Risk"] = "MEDIUM"
    latest["Model_Version"] = VERSION
    latest["Dataset_Version"] = "phase1-v1-clean-v3"
    latest.to_parquet(DATA / "wastage_next_week.parquet", index=False)
    actual_risk = holdout.Actual_High_Risk
    predicted_risk = holdout.Predicted_High_Risk
    baseline_risk = holdout.Baseline.gt(high_cut)
    metrics = {"version": VERSION, "dataset_version": "phase1-v1-clean-v3", "cutoff": str(cutoff.date()),
        "holdout_cases": len(holdout), "high_risk_threshold": high_cut,
        "target_grain": "observed item/location/week wastage subtotal",
        "observed_week_rows": len(observed), "unobserved_week_rows": int(data.Wasted.isna().sum()),
        "preprocessing_version": PREPROCESSING_VERSION, "missing_week_policy": MISSING_WEEK_POLICY,
        "feature_names": FEATURES, "status": "EXPERIMENTAL",
        "training_range": [str(training.Week.min().date()), str(training.Week.max().date())],
        "validation_range": [str(validation.Week.min().date()), str(validation.Week.max().date())],
        "test_range": [str(holdout.Week.min().date()), str(holdout.Week.max().date())],
        "training_cases": len(training), "validation_cases": len(validation),
        "validation_risk_f1": validation_f1,
        "validation_mae": mean_absolute_error(validation.Wasted, validation.Predicted_Wastage),
        "validation_rmse": mean_squared_error(validation.Wasted, validation.Predicted_Wastage) ** .5,
        "validation_baseline_mae": mean_absolute_error(validation.Wasted, validation.Baseline),
        "validation_baseline_rmse": mean_squared_error(validation.Wasted, validation.Baseline) ** .5,
        "risk_probability_threshold": threshold,
        "mae": mean_absolute_error(holdout.Wasted, holdout.Predicted_Wastage),
        "rmse": mean_squared_error(holdout.Wasted, holdout.Predicted_Wastage) ** .5,
        "baseline_mae": mean_absolute_error(holdout.Wasted, holdout.Baseline),
        "baseline_rmse": mean_squared_error(holdout.Wasted, holdout.Baseline) ** .5,
        "high_risk_accuracy": accuracy_score(actual_risk, predicted_risk),
        "high_risk_precision": precision_score(actual_risk, predicted_risk, zero_division=0),
        "high_risk_recall": recall_score(actual_risk, predicted_risk, zero_division=0),
        "high_risk_f1": f1_score(actual_risk, predicted_risk, zero_division=0),
        "baseline_high_risk_accuracy": accuracy_score(actual_risk, baseline_risk),
        "baseline_high_risk_precision": precision_score(actual_risk, baseline_risk, zero_division=0),
        "baseline_high_risk_recall": recall_score(actual_risk, baseline_risk, zero_division=0),
        "baseline_high_risk_f1": f1_score(actual_risk, baseline_risk, zero_division=0),
        "high_risk_predicted_cases": int(holdout.Predicted_High_Risk.sum()),
        "high_risk_actual_cases": int(holdout.Actual_High_Risk.sum())}
    joblib.dump({"model": model, "risk_model": risk_model, "risk_probability_threshold": threshold,
                 "features": FEATURES, "version": VERSION, "preprocessing_version": PREPROCESSING_VERSION,
                 "missing_week_policy": MISSING_WEEK_POLICY,
                 "dataset_version": "phase1-v1-clean-v3", "high_risk_threshold": high_cut,
                 "training_range": metrics["training_range"], "validation_range": metrics["validation_range"],
                 "test_range": metrics["test_range"], "metrics": metrics},
                OUT / "wastage_weekly_model.joblib")
    (OUT / "wastage_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    train()
