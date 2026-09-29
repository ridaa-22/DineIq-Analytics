"""Forecast features use prior demand, including on recursive horizons."""

import unittest

import numpy as np
import pandas as pd

from Python_Pipeline.forecast_features import FEATURES, daily_series, feature_frame, recursive_forecast


class IncrementModel:
    def predict(self, rows):
        return np.asarray(rows.lag_1, dtype=float) + 1


class GrainForecastTests(unittest.TestCase):
    def test_features_shift_before_rolling(self):
        daily = pd.DataFrame({"Date": pd.date_range("2025-01-01", periods=9),
                              "Entity_ID": [1] * 9, "Demand": range(1, 10)})
        features = feature_frame(daily)
        self.assertEqual(features[FEATURES].iloc[0].lag_1, 7)
        self.assertEqual(features[FEATURES].iloc[0].lag_7, 1)
        self.assertEqual(features[FEATURES].iloc[0].rolling_7, 4)

    def test_recursive_forecast_uses_prior_predictions(self):
        result = recursive_forecast(IncrementModel(), {42: list(range(1, 8))}, "2025-01-08", 14)
        self.assertEqual(result.Prediction.tolist(), list(range(8, 22)))
        self.assertEqual(result.Baseline.iloc[0], 1)
        self.assertEqual(result.Baseline.iloc[7], 1)

    def test_new_item_has_no_false_pre_introduction_zeros(self):
        item = daily_series("item")
        item = item[item.Entity_ID.eq(9)]
        self.assertEqual(str(item.Date.min().date()), "2025-12-01")
        self.assertGreaterEqual(item.Demand.min(), 0)


if __name__ == "__main__":
    unittest.main()
