"""Shared weekly wastage feature contract for fitting, scoring, and inference."""

import numpy as np
import pandas as pd


PREPROCESSING_VERSION = "observed-week-history-v1"
MISSING_WEEK_POLICY = "Absent wastage and preparation are unavailable (NaN); four-week wastage mean requires four observed weeks. Missing sales demand is zero."
FEATURES = ["Item_ID", "Location_ID", "month", "week_of_year", "lag_waste_1",
            "lag_waste_4", "rolling_waste_4", "lag_demand_1", "rolling_demand_4", "lag_prepared_1"]
BASE_COLUMNS = ["Item_ID", "Location_ID", "Week", "Wasted", "Prepared", "Demand"]


def build_wastage_features(grid):
    """Build strictly prior-week features, preserving unknown observed outcomes."""
    data = grid[BASE_COLUMNS].sort_values(["Item_ID", "Location_ID", "Week"]).copy()
    data["Demand"] = data.Demand.fillna(0)
    group = data.groupby(["Item_ID", "Location_ID"], sort=False)
    for name, source, lag in (("lag_waste_1", "Wasted", 1), ("lag_waste_4", "Wasted", 4),
                              ("lag_demand_1", "Demand", 1), ("lag_prepared_1", "Prepared", 1)):
        data[name] = group[source].shift(lag)
    data["rolling_waste_4"] = group.Wasted.transform(lambda values: values.shift(1).rolling(4, min_periods=4).mean())
    data["rolling_demand_4"] = group.Demand.transform(lambda values: values.shift(1).rolling(4, min_periods=4).mean())
    data["last_observed_waste"] = group.Wasted.transform(lambda values: values.ffill().shift(1))
    data["month"] = data.Week.dt.month
    data["week_of_year"] = data.Week.dt.isocalendar().week.astype(int)
    return data


def build_next_week_features(history):
    """Append an unobserved next week and run the exact training builder."""
    last_week = history.Week.max()
    pairs = history[["Item_ID", "Location_ID"]].drop_duplicates()
    future = pairs.assign(Week=last_week + pd.Timedelta(weeks=1), Wasted=np.nan,
                          Prepared=np.nan, Demand=np.nan)
    built = build_wastage_features(pd.concat([history[BASE_COLUMNS], future], ignore_index=True))
    return built[built.Week.eq(last_week + pd.Timedelta(weeks=1))].copy()
