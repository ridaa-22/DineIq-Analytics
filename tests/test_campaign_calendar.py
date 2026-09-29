"""Campaign population and restaurant-day boundaries."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from Python_Pipeline.business_time import local_dates, local_day_after, local_day_start
from Python_Pipeline.campaign_eligibility import get_eligible_sales_for_promotion
from fast_apis.routes import dynamic
from fast_apis.routes.dynamic import frame, promotions


class CampaignCalendarTests(unittest.TestCase):
    def test_item_target_excludes_same_category_and_location_intersects(self):
        sales = pd.DataFrame({"Item_ID": [4, 5, 4], "Category_ID": [4, 4, 4],
                              "Location_ID": [1, 1, 2], "Order_DateTime": pd.to_datetime([
                                  "2025-06-01T00:00:00+05:00"] * 3, utc=True).tz_convert("Asia/Karachi")})
        campaign = {"applicable_item_id": 4, "applicable_category_id": 4,
                    "location_id": 1, "start_date": "2025-06-01", "end_date": "2025-06-30"}
        eligible = get_eligible_sales_for_promotion(sales, campaign, during=True)
        self.assertEqual(eligible.index.tolist(), [0])
        self.assertEqual(get_eligible_sales_for_promotion(sales,
            {"applicable_item_id": None, "applicable_category_id": 4}).index.tolist(), [0, 1, 2])
        self.assertEqual(get_eligible_sales_for_promotion(sales,
            {"applicable_item_id": None, "applicable_category_id": None}).index.tolist(), [0, 1, 2])

    def test_local_midnight_boundaries(self):
        times = pd.to_datetime(["2025-05-31T23:59:00+05:00", "2025-06-01T00:00:00+05:00",
                                "2025-06-30T23:59:00+05:00", "2025-07-01T00:00:00+05:00"], utc=True).tz_convert("Asia/Karachi")
        sales = pd.DataFrame({"Item_ID": [4] * 4, "Category_ID": [4] * 4,
                              "Location_ID": [1] * 4, "Order_DateTime": times})
        campaign = {"applicable_item_id": 4, "start_date": "2025-06-01", "end_date": "2025-06-30"}
        self.assertEqual(get_eligible_sales_for_promotion(sales, campaign, during=True).index.tolist(), [1, 2])
        self.assertEqual(local_dates(sales.Order_DateTime).astype(str).tolist(),
                         ["2025-05-31", "2025-06-01", "2025-06-30", "2025-07-01"])
        self.assertEqual(local_day_start("2025-06-01").isoformat(), "2025-06-01T00:00:00+05:00")
        self.assertEqual(local_day_after("2025-06-30").isoformat(), "2025-07-01T00:00:00+05:00")
        with patch.object(dynamic, "frame", return_value=sales):
            filtered = dynamic.sales_for({"roles": ["ADMIN"]}, date_from="2025-06-01", date_to="2025-06-30")
        self.assertEqual(filtered.index.tolist(), [1, 2])

    def test_campaign_one_population_matches_item_four(self):
        from fast_apis import database
        with tempfile.TemporaryDirectory() as folder, patch.object(database, "DB_PATH", Path(folder) / "app.sqlite3"):
            with database.connection() as db:
                campaign = dict(db.execute("SELECT * FROM promotions WHERE promotion_id=1").fetchone())
            eligible = get_eligible_sales_for_promotion(frame("sales"), campaign)
            self.assertEqual(set(eligible.Item_ID), {4})
            output = next(row for row in promotions(user={"roles": ["ADMIN"]})["campaigns"]
                          if row["Promotion_ID"] == 1)
            self.assertEqual(output["eligible_item_count"], 1)
