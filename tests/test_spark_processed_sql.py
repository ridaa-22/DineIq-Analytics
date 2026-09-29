"""Spark joins retain sale-line grain and reconcile with clean economics."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from spark_jobs.ingest import create_spark, sha256
from spark_jobs.processed_sql import QUERIES, build_views, register_sources, validate
from Python_Pipeline.build_processed import PARQUET_OPTIONS


class ProcessedSparkSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = create_spark("DineIQ-Processed-SQL-Tests")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        stamp = pd.Timestamp("2025-07-01T00:00:00+05:00")
        rows = {
            "orders_validated": [{"Order_ID": 1, "Customer_ID": 1, "Location_ID": 1,
                "Order_DateTime": stamp, "Channel": "App", "Promotion_ID": 1, "Order_Status": "Completed"}],
            "customers_validated": [{"Customer_ID": 1, "Customer_Name": "Customer"}],
            "order_items_validated": [
                {"Order_Item_ID": 1, "Order_ID": 1, "Item_ID": 4, "Quantity": 2,
                 "Unit_Price": 100.0, "Discount_Applied": 40.0},
                {"Order_Item_ID": 2, "Order_ID": 1, "Item_ID": 21, "Quantity": 1,
                 "Unit_Price": 50.0, "Discount_Applied": 0.0}],
            "menu_items_validated": [{"Item_ID": 4, "Item_Name": "Target", "Category_ID": 4, "Cost": 60.0},
                                     {"Item_ID": 21, "Item_Name": "Other", "Category_ID": 4, "Cost": 20.0}],
            "menu_categories_validated": [{"Category_ID": 4, "Category_Name": "Shared"}],
            "restaurant_locations_validated": [{"Location_ID": 1, "Location_Name": "A", "City": "Karachi"}],
            "promotions_validated": [{"Promotion_ID": 1, "Promotion_Name": "Item four",
                "Discount_Percent": 20, "Start_Date": "2025-07-01", "End_Date": "2025-07-31",
                "Applicable_Item_ID": 4, "Applicable_Category_ID": 4}],
            "pricing_history_validated": [{"Pricing_ID": 1, "Item_ID": 4, "Price": 90.0, "Effective_Date": "2025-01-01"},
                {"Pricing_ID": 2, "Item_ID": 4, "Price": 100.0, "Effective_Date": "2025-07-01"},
                {"Pricing_ID": 3, "Item_ID": 21, "Price": 50.0, "Effective_Date": "2025-01-01"}],
            "ratings": [{"Rating_ID": 1, "Order_ID": 1, "Item_ID": 4, "Stars": 4},
                        {"Rating_ID": 2, "Order_ID": 1, "Item_ID": 4, "Stars": 5}],
            "inventory_validated": [{"Inventory_ID": 1, "Item_ID": 4, "Location_ID": 1,
                "Period_End": "2025-06-30", "Stock_Quantity": 10, "Reorder_Level": 2},
                {"Inventory_ID": 2, "Item_ID": 4, "Location_ID": 1,
                 "Period_End": "2025-07-31", "Stock_Quantity": 5, "Reorder_Level": 2}],
            "wastage": [{"Wastage_ID": 1, "Item_ID": 4, "Location_ID": 1,
                "Quantity_Wasted": 2, "Cost_Impact": 120.0},
                {"Wastage_ID": 2, "Item_ID": 4, "Location_ID": 1,
                 "Quantity_Wasted": 3, "Cost_Impact": 180.0}],
            "sales": [{"Net_Revenue": 160.0, "Cost_Total": 120.0, "Contribution": 40.0},
                      {"Net_Revenue": 50.0, "Cost_Total": 20.0, "Contribution": 30.0}],
        }
        for name, data in rows.items():
            pd.DataFrame(data).to_parquet(self.root / f"{name}.parquet", index=False, **PARQUET_OPTIONS)
        (self.root / "quality_report.json").write_text(json.dumps({
            "dataset_version": "phase1-v1-clean-v3", "clean_completed_lines": 2}))
        (self.root / "spark_snapshot_manifest.json").write_text(json.dumps({
            "dataset_version": "phase1-v1-clean-v3", "source_raw_manifest_sha256": "fixture",
            "files": {path.name: sha256(path) for path in self.root.glob("*.parquet")}}))
        self.quality = register_sources(self.spark, self.root)
        build_views(self.spark)

    def tearDown(self):
        self.temp.cleanup()

    def test_join_grain_financial_totals_and_sql_queries(self):
        rows = self.spark.sql("""SELECT Order_Item_ID,Item_ID,Effective_Price,Rating_Count,
            Wastage_Quantity,Stock_Quantity,Net_Revenue,Cost_Total,Contribution,Campaign_Eligible
            FROM integrated_sales ORDER BY Order_Item_ID""").collect()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row.Order_Item_ID for row in rows], [1, 2])
        self.assertEqual(float(rows[0].Effective_Price), 100)
        self.assertEqual(rows[0].Rating_Count, 2)
        self.assertEqual(rows[0].Wastage_Quantity, 5)
        self.assertEqual(rows[0].Stock_Quantity, 5)
        self.assertEqual([bool(row.Campaign_Eligible) for row in rows], [True, False])
        self.assertEqual((float(rows[0].Net_Revenue), float(rows[0].Cost_Total),
                          float(rows[0].Contribution)), (160, 120, 40))
        self.assertEqual(validate(self.spark, self.quality)["joined_rows"], 2)
        category = self.spark.sql(QUERIES["categories_sql.csv"]).first()
        self.assertEqual(category.Units, 3)
        self.assertEqual(float(category.Contribution), 70)
        campaign = self.spark.sql(QUERIES["campaigns_sql.csv"]).first()
        self.assertEqual(campaign.Units, 2)
        self.assertEqual(float(campaign.Net_Revenue), 160)
        self.assertEqual(self.spark.sql(QUERIES["high_wastage_sql.csv"]).first().Wastage_Quantity, 5)

    def test_missing_customer_fails_integrity_gate(self):
        self.spark.sql("SELECT 999 AS Customer_ID, 'Unrelated' AS Customer_Name").createOrReplaceTempView("clean_customers")
        build_views(self.spark)
        with self.assertRaisesRegex(ValueError, "join rows"):
            validate(self.spark, self.quality)

    def test_stale_snapshot_is_rejected(self):
        with (self.root / "menu_items_validated.parquet").open("ab") as target:
            target.write(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            register_sources(self.spark, self.root)
