"""Shared daily demand and prediction-time features for location, item, and category."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "phase1-v1"
FEATURES = ["Entity_ID", "day_of_week", "month", "lag_1", "lag_7", "rolling_7"]
GRAINS = {"location": "Location_ID", "item": "Item_ID", "category": "Category_ID"}
HORIZONS = (1, 7, 14, 30)


def daily_series(grain):
    """Return complete active entity-days; an active day without sales has zero demand."""
    if grain not in GRAINS:
        raise ValueError(f"Unknown forecast grain: {grain}")
    if grain == "location":
        source = pd.read_parquet(PROCESSED / "location_daily.parquet")
        daily = source[["Date", "Location_ID", "Demand"]].rename(columns={"Location_ID": "Entity_ID"})
        starts = daily.groupby("Entity_ID").Date.min()
    else:
        sales = pd.read_parquet(PROCESSED / "sales.parquet",
                                columns=["Date", GRAINS[grain], "Quantity"])
        daily = (sales.groupby(["Date", GRAINS[grain]], as_index=False).Quantity.sum()
                 .rename(columns={GRAINS[grain]: "Entity_ID", "Quantity": "Demand"}))
        if grain == "item":
            menu = pd.read_parquet(PROCESSED / "menu_items_validated.parquet",
                                   columns=["Item_ID", "Introduced_Date"])
            starts = menu.set_index("Item_ID").Introduced_Date
        else:
            starts = daily.groupby("Entity_ID").Date.min()
    daily["Date"] = pd.to_datetime(daily.Date)
    starts = pd.to_datetime(starts)
    last = daily.Date.max()
    full = []
    for entity_id, first in starts.items():
        first = max(pd.Timestamp(first), daily.Date.min())
        full.append(pd.DataFrame({"Date": pd.date_range(first, last), "Entity_ID": int(entity_id)}))
    calendar = pd.concat(full, ignore_index=True)
    result = calendar.merge(daily, on=["Date", "Entity_ID"], how="left", validate="one_to_one")
    result["Demand"] = result.Demand.fillna(0).astype(float)
    return result.sort_values(["Entity_ID", "Date"]).reset_index(drop=True)


def feature_frame(daily):
    result = daily.sort_values(["Entity_ID", "Date"]).copy()
    grouped = result.groupby("Entity_ID").Demand
    result["lag_1"] = grouped.shift(1)
    result["lag_7"] = grouped.shift(7)
    result["rolling_7"] = grouped.transform(lambda values: values.shift(1).rolling(7).mean())
    result["day_of_week"] = result.Date.dt.dayofweek
    result["month"] = result.Date.dt.month
    return result.dropna(subset=FEATURES).copy()


def recursive_forecast(model, histories, start_date, horizon):
    """Advance only on predictions; neither model nor baseline sees future actuals."""
    model_history = {int(key): list(value) for key, value in histories.items() if len(value) >= 7}
    baseline_history = {key: values.copy() for key, values in model_history.items()}
    if not model_history:
        return pd.DataFrame(columns=["Date", "Entity_ID", "Lead", "Prediction", "Baseline"])
    output = []
    for lead in range(1, horizon + 1):
        date = pd.Timestamp(start_date) + pd.Timedelta(days=lead - 1)
        rows = [{"Entity_ID": entity_id, "day_of_week": date.dayofweek, "month": date.month,
                 "lag_1": values[-1], "lag_7": values[-7],
                 "rolling_7": float(np.mean(values[-7:]))}
                for entity_id, values in model_history.items()]
        features = pd.DataFrame(rows)[FEATURES]
        predictions = np.maximum(0, model.predict(features))
        for row, prediction in zip(rows, predictions):
            entity_id = row["Entity_ID"]
            baseline = float(baseline_history[entity_id][-7])
            output.append({"Date": date, "Entity_ID": entity_id, "Lead": lead,
                           "Prediction": float(prediction), "Baseline": baseline})
            model_history[entity_id].append(float(prediction))
            baseline_history[entity_id].append(baseline)
    return pd.DataFrame(output)


def histories_before(daily, cutoff):
    earlier = daily[daily.Date.le(pd.Timestamp(cutoff))]
    return {int(entity_id): group.sort_values("Date").Demand.to_numpy(dtype=float).tolist()
            for entity_id, group in earlier.groupby("Entity_ID")}
