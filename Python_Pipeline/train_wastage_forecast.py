"""Next-week wastage forecast using only past-known weekly features."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import f1_score, mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "phase1-v1"
OUT = ROOT / "Models" / "integrated"
FEATURES = ["Item_ID", "Location_ID", "month", "week_of_year", "lag_waste_1",
            "lag_waste_4", "rolling_waste_4", "lag_demand_1", "rolling_demand_4", "lag_prepared_1"]
VERSION = "weekly-wastage-hgb-v5"


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
        demand, on=["Item_ID", "Location_ID", "Week"], how="left").fillna({"Demand": 0})
    data = data.sort_values(["Item_ID", "Location_ID", "Week"])
    group = data.groupby(["Item_ID", "Location_ID"])
    for name, source, lag in (("lag_waste_1", "Wasted", 1), ("lag_waste_4", "Wasted", 4),
                              ("lag_demand_1", "Demand", 1), ("lag_prepared_1", "Prepared", 1)):
        data[name] = group[source].shift(lag)
    data["rolling_waste_4"] = group.Wasted.transform(lambda values: values.shift(1).rolling(4).mean())
    data["rolling_demand_4"] = group.Demand.transform(lambda values: values.shift(1).rolling(4).mean())
    data["last_observed_waste"] = group.Wasted.transform(lambda values: values.ffill().shift(1))
    data["month"] = data.Week.dt.month
    data["week_of_year"] = data.Week.dt.isocalendar().week.astype(int)
    return data.copy()


def train():
    OUT.mkdir(parents=True, exist_ok=True)
    data = weekly_frame()
    cutoff = data.Week.max() - pd.Timedelta(weeks=8)
    # The source is a sample of observed item/location/days. An absent record
    # is unknown, not a measured zero. Train and score observed weeks only.
    observed = data[data.Wasted.notna()].copy()
    training = observed[observed.Week.le(cutoff)]
    holdout = observed[observed.Week.gt(cutoff)].copy()
    validation_start = cutoff - pd.Timedelta(weeks=8)
    classifier_train = training[training.Week.le(validation_start)]
    classifier_validation = training[training.Week.gt(validation_start)]
    model = HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=25, l2_regularization=1,
                                          random_state=42).fit(training[FEATURES], training.Wasted)
    holdout["Predicted_Wastage"] = np.maximum(0, model.predict(holdout[FEATURES]))
    holdout["Baseline"] = holdout.last_observed_waste.fillna(0)
    high_cut = float(classifier_train.loc[classifier_train.Wasted.gt(0), "Wasted"].quantile(.75))
    risk_model = HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=25,
        l2_regularization=1, random_state=42).fit(classifier_train[FEATURES],
                                                   classifier_train.Wasted.gt(high_cut))
    validation_probabilities = risk_model.predict_proba(classifier_validation[FEATURES])[:, 1]
    thresholds = np.arange(.1, .91, .05)
    threshold = float(max(thresholds, key=lambda value: f1_score(
        classifier_validation.Wasted.gt(high_cut), validation_probabilities >= value,
        zero_division=0)))
    validation_f1 = float(f1_score(classifier_validation.Wasted.gt(high_cut),
                                   validation_probabilities >= threshold, zero_division=0))
    risk_model.fit(training[FEATURES], training.Wasted.gt(high_cut))
    holdout["Actual_High_Risk"] = holdout.Wasted.gt(high_cut)
    holdout["Risk_Probability"] = risk_model.predict_proba(holdout[FEATURES])[:, 1]
    holdout["Predicted_High_Risk"] = holdout.Risk_Probability.ge(threshold)
    holdout["Case_ID"] = holdout.Week.dt.strftime("%Y-%m-%d") + ":" + holdout.Item_ID.astype(str) + ":" + holdout.Location_ID.astype(str)
    holdout.to_parquet(OUT / "wastage_holdout.parquet", index=False)
    next_week = data.Week.max() + pd.Timedelta(weeks=1)
    last_week = data.Week.max()
    history = data[data.Week.gt(last_week - pd.Timedelta(weeks=4))]
    recent = history.groupby(["Item_ID", "Location_ID"]).agg(
        rolling_waste_4=("Wasted", "mean"),
        rolling_demand_4=("Demand", "mean")).reset_index()
    fourth = data[data.Week.eq(last_week - pd.Timedelta(weeks=3))][
        ["Item_ID", "Location_ID", "Wasted"]].rename(columns={"Wasted": "lag_waste_4"})
    latest = data[data.Week.eq(last_week)][["Item_ID", "Location_ID", "Wasted", "Demand", "Prepared"]].rename(
        columns={"Wasted": "lag_waste_1", "Demand": "lag_demand_1", "Prepared": "lag_prepared_1"})
    latest = latest.merge(recent, on=["Item_ID", "Location_ID"]).merge(
        fourth, on=["Item_ID", "Location_ID"], how="left")
    latest["Week"] = next_week
    latest["month"] = next_week.month
    latest["week_of_year"] = next_week.isocalendar().week
    latest["Expected_Wastage"] = np.maximum(0, model.predict(latest[FEATURES]))
    latest["Risk_Probability"] = risk_model.predict_proba(latest[FEATURES])[:, 1]
    latest["Risk"] = pd.cut(latest.Expected_Wastage, [-1, high_cut * .5, high_cut, float("inf")],
                            labels=["LOW", "MEDIUM", "HIGH"]).astype(str)
    latest.loc[latest.Risk_Probability.ge(threshold), "Risk"] = "HIGH"
    latest.loc[latest.Risk_Probability.lt(threshold) & latest.Risk.eq("HIGH"), "Risk"] = "MEDIUM"
    latest["Model_Version"] = VERSION
    latest["Dataset_Version"] = "phase1-v1-clean-v3"
    latest.to_parquet(DATA / "wastage_next_week.parquet", index=False)
    joblib.dump({"model": model, "risk_model": risk_model, "risk_probability_threshold": threshold,
                 "features": FEATURES, "version": VERSION,
                 "dataset_version": "phase1-v1-clean-v3", "high_risk_threshold": high_cut},
                OUT / "wastage_weekly_model.joblib")
    metrics = {"version": VERSION, "dataset_version": "phase1-v1-clean-v3", "cutoff": str(cutoff.date()),
        "holdout_cases": len(holdout), "high_risk_threshold": high_cut,
        "target_grain": "observed item/location/week wastage subtotal",
        "observed_week_rows": len(observed), "unobserved_week_rows": int(data.Wasted.isna().sum()),
        "validation_cases": len(classifier_validation), "validation_risk_f1": validation_f1,
        "risk_probability_threshold": threshold,
        "mae": mean_absolute_error(holdout.Wasted, holdout.Predicted_Wastage),
        "rmse": mean_squared_error(holdout.Wasted, holdout.Predicted_Wastage) ** .5,
        "baseline_mae": mean_absolute_error(holdout.Wasted, holdout.Baseline),
        "high_risk_precision": float((holdout.Actual_High_Risk & holdout.Predicted_High_Risk).sum() /
            max(holdout.Predicted_High_Risk.sum(), 1)),
        "high_risk_recall": float((holdout.Actual_High_Risk & holdout.Predicted_High_Risk).sum() /
            max(holdout.Actual_High_Risk.sum(), 1)),
        "high_risk_predicted_cases": int(holdout.Predicted_High_Risk.sum()),
        "high_risk_actual_cases": int(holdout.Actual_High_Risk.sum())}
    (OUT / "wastage_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    train()
