"""Contradictory business cases and temporal safeguards, not implementation mirrors."""

import unittest
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from Python_Pipeline.business_windows import promotion_trap, sensitivity
from Python_Pipeline.menu_scoring import classify_items
from Python_Pipeline.train_customer_segments import business_labels
from Python_Pipeline.train_wastage_forecast import FEATURES, weekly_frame
from fast_apis.routes.dynamic import anomalies, pricing, promotions, frame


ADMIN = {"id": 1, "roles": ["ADMIN"], "location_ids": []}


class BusinessMethodTests(unittest.TestCase):
    def test_invalid_raw_base_price_does_not_erase_valid_historical_sales(self):
        root = Path(__file__).resolve().parents[1]
        raw = pd.read_csv(root / "data/raw/phase1-v1/Menu_Items.csv")
        invalid_ids = set(raw.loc[raw.Base_Price.le(0), "Item_ID"])
        self.assertEqual(len(invalid_ids), 5)
        sales = frame("sales")
        self.assertTrue(invalid_ids.issubset(set(sales.Item_ID)))
        self.assertTrue(sales.loc[sales.Item_ID.isin(invalid_ids), "Unit_Price"].gt(0).all())
        anchor = sales[sales.Order_ID.eq(1)].iloc[0]
        self.assertEqual(str(anchor.Order_DateTime.tz), "Asia/Karachi")
        self.assertEqual(anchor.Date, "2025-01-01")

    def test_partitioned_sales_are_complete_for_spark_sql(self):
        root = Path(__file__).resolve().parents[1] / "data/processed/phase1-v1"
        metadata = json.loads((root / "partition_strategy.json").read_text(encoding="utf-8"))
        files = list((root / "sales_by_location").glob("Location_ID=*/part.parquet"))
        self.assertEqual(len(files), 20)
        partition_rows = sum(pq.ParquetFile(path).metadata.num_rows for path in files)
        self.assertEqual(partition_rows, pq.ParquetFile(root / "sales.parquet").metadata.num_rows)
        self.assertEqual(partition_rows, sum(metadata["rows_by_location"].values()))

    def test_quality_report_separates_detected_defects_from_clean_output(self):
        root = Path(__file__).resolve().parents[1] / "data/processed/phase1-v1"
        report = json.loads((root / "quality_report.json").read_text(encoding="utf-8"))
        conditions = report["detected_conditions"]
        self.assertEqual(conditions["duplicate_order_headers"], 80)
        self.assertEqual(conditions["invalid_line_quantities"], 150)
        self.assertEqual(conditions["invalid_base_prices"], 5)
        self.assertEqual(report["valid_menu_items"], 150)
        self.assertEqual(report["clean_completed_lines"], report["partitioned_sales_lines"])
        self.assertIn("effective price-history", report["cleaning_rules"]["menu"])

    def test_menu_contradictions_do_not_become_profit_drivers(self):
        cases = pd.DataFrame([
            (1, 1000, 40, 40000, 4.5, 100, 10, .35, .05, 12, 80, 365),
            (2, 900, -10, -9000, 4.2, 100, 5, .30, .08, 2, 70, 365),
            (3, 700, 30, 21000, 4.0, 100, 300, .25, .05, 3, 60, 365),
            (4, 50, 60, 3000, 4.8, 30, 1, .32, .02, 20, 15, 365),
            (5, 20, -5, -100, 2.0, 20, 8, .01, .60, -50, 10, 10),
        ], columns=["Item_ID", "sales", "profit_percent", "contribution", "Average_Rating",
                    "Rating_Count", "wastage_quantity", "repeat_purchase_rate", "promotion_dependency",
                    "sales_trend_percent", "orders", "active_days"])
        labeled = classify_items(cases).set_index("Item_ID")
        self.assertEqual(labeled.loc[1, "classification"], "Profit Driver")
        self.assertEqual(labeled.loc[2, "classification"], "Volume Driver")
        self.assertEqual(labeled.loc[3, "classification"], "Volume Driver")
        self.assertEqual(labeled.loc[4, "classification"], "Hidden Opportunity")
        self.assertTrue(labeled.loc[5, "insufficient_history"])
        self.assertIn("wastage_percent", labeled.loc[3, "classification_evidence"])

    def test_real_price_and_promotion_trap(self):
        price = pricing(item_id=6, limit=10, user=ADMIN)["observations"]
        self.assertEqual(len(price), 1)
        self.assertEqual(price[0]["Sensitivity"], "HIGH")
        self.assertGreater(price[0]["Observed_Price_Change_Percent"], 30)
        campaigns = promotions(user=ADMIN)["campaigns"]
        self.assertTrue(next(c for c in campaigns if c["Promotion_ID"] == 1)["promotion_trap"])
        self.assertIsNone(promotion_trap({"orders": 0}, {"orders": 5}))
        self.assertEqual(sensitivity(100, 100, 50, 20), "NOT VERIFIABLE")

    def test_clean_rfm_uses_distinct_orders_and_net_spend(self):
        sales = frame("sales")
        rfm = frame("customer_rfm")
        customer_id = int(rfm.Customer_ID.iloc[0])
        own = sales[sales.Customer_ID.eq(customer_id)]
        saved = rfm[rfm.Customer_ID.eq(customer_id)].iloc[0]
        self.assertEqual(int(saved.Frequency), own.Order_ID.nunique())
        self.assertAlmostEqual(float(saved.Monetary), float(own.Net_Revenue.sum()), places=2)

    def test_cluster_name_respects_recency_even_with_repeat_orders(self):
        profiles = pd.DataFrame({"Recency_Days": [224, 21, 13, 28, 152],
                                 "Frequency": [1.0, 2.4, 22.5, 1.0, 2.2],
                                 "Monetary": [15000, 38000, 348000, 15600, 34600]},
                                index=[0, 1, 2, 3, 4])
        labels = business_labels(profiles)
        self.assertEqual(labels[0], "At Risk")
        self.assertEqual(labels[2], "High Value")
        self.assertEqual(labels[4], "Cooling")

    def test_wastage_features_are_prior_period_only(self):
        self.assertNotIn("Wasted", FEATURES)
        self.assertNotIn("Prepared", FEATURES)
        weekly = weekly_frame()
        pair = weekly[(weekly.Item_ID.eq(3)) & (weekly.Location_ID.eq(1))].sort_values("Week")
        self.assertGreater(len(pair), 4)
        self.assertEqual(float(pair.lag_waste_1.iloc[1]), float(pair.Wasted.iloc[0]))
        self.assertGreater(int(weekly.Wasted.isna().sum()), 0)
        self.assertTrue(weekly.loc[weekly.Wasted.isna(), "Prepared"].isna().all())

    def test_rating_and_sales_anomalies_are_behavioral(self):
        flags = anomalies(user=ADMIN)
        self.assertTrue(flags["sales"])
        self.assertTrue(any(row["Item_ID"] == 13 for row in flags["ratings"]))
        self.assertTrue(all(1 <= row["average_stars"] <= 5 for row in flags["ratings"]))


if __name__ == "__main__":
    unittest.main()
