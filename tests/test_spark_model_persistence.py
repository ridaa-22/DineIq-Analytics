"""Integration check for the persisted selected Spark location model."""

import json
import unittest

from scripts.reload_spark_location_forecast import ROOT, reload_and_check


class SparkModelPersistenceTests(unittest.TestCase):
    def test_manifest_and_fresh_load_prediction(self):
        model_root = ROOT / "Models" / "spark" / "location_forecast" / "spark-location-selected-v4"
        manifest = json.loads((model_root / "manifest.json").read_text(encoding="utf-8"))
        for key in ("model_name", "model_version", "dataset_version", "algorithm", "features",
                    "training_range", "validation_range", "test_range", "metrics", "created_at"):
            self.assertIn(key, manifest)
        self.assertEqual(manifest["algorithm"], "RandomForestRegressor")
        self.assertEqual(reload_and_check()["matched"], True)


if __name__ == "__main__":
    unittest.main()
