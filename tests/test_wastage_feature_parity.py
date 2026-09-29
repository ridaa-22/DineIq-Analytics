"""Training and next-week scoring must use identical historical features."""

import unittest

import joblib
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from Python_Pipeline.train_wastage_forecast import DATA, OUT, weekly_frame
from Python_Pipeline.wastage_features import (FEATURES, PREPROCESSING_VERSION,
    build_next_week_features, build_wastage_features)


class WastageFeatureParityTests(unittest.TestCase):
    def test_representative_and_missing_week_vectors_match(self):
        weeks = pd.date_range("2025-01-06", periods=7, freq="W-MON")
        for wastes in ([1, 2, 3, 4, 5, 6, 7], [1, np.nan, 3, 4, 5, 6, 7]):
            with self.subTest(wastes=wastes):
                grid = pd.DataFrame({"Item_ID": [4] * 7, "Location_ID": [1] * 7,
                    "Week": weeks, "Wasted": wastes, "Prepared": [10] * 7, "Demand": [8] * 7})
                training = build_wastage_features(grid).iloc[[5]][FEATURES].reset_index(drop=True)
                inference = build_next_week_features(grid.iloc[:5])[FEATURES].reset_index(drop=True)
                assert_frame_equal(training, inference, check_dtype=False)
                if np.isnan(wastes[1]):
                    self.assertTrue(np.isnan(training.rolling_waste_4.iloc[0]))
                else:
                    self.assertEqual(training.rolling_waste_4.iloc[0], 3.5)

    def test_real_missing_week_semantics_and_saved_model(self):
        data = weekly_frame()
        future = build_next_week_features(data)
        self.assertEqual(len(future), 3000)
        last_four = data[data.Week.gt(data.Week.max() - pd.Timedelta(weeks=4))]
        permissive = last_four.groupby(["Item_ID", "Location_ID"]).Wasted.mean().reset_index(name="permissive")
        comparison = future.merge(permissive, on=["Item_ID", "Location_ID"])
        self.assertEqual(int((comparison.permissive.notna() & comparison.rolling_waste_4.isna()).sum()), 2047)
        artifact = joblib.load(OUT / "wastage_weekly_model.joblib")
        self.assertEqual(artifact["preprocessing_version"], PREPROCESSING_VERSION)
        self.assertEqual(artifact["features"], FEATURES)
        prediction = artifact["model"].predict(future[FEATURES].head(3))
        self.assertEqual(len(prediction), 3)
        self.assertTrue(np.isfinite(prediction).all())
        self.assertTrue((DATA / "wastage_next_week.parquet").is_file())
