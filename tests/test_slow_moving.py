"""Exact multifactor and context cases from the Phase 7 acceptance gate."""

import unittest

import pandas as pd

from Python_Pipeline.slow_moving import analyze_slow_moving


def item(item_id, sales, orders, **changes):
    row = {"Item_ID": item_id, "Location_ID": None, "sales": sales, "orders": orders,
           "history_days": 365, "days_since_last_purchase": 2,
           "sales_trend_percent": 10, "repeat_purchase_rate": .25,
           "profit_percent": 50, "contribution": 1000,
           "wastage_percent": 3, "seasonal_top3_share": .35, "active_months": 12,
           "Average_Rating": 4.2, "Rating_Count": 20}
    row.update(changes)
    return row


class SlowMovingTests(unittest.TestCase):
    def test_profitable_new_seasonal_and_declining_cases(self):
        rows = [
            item(1, 2, 2, profit_percent=90, contribution=500, repeat_purchase_rate=.2),
            item(2, 3, 2, history_days=20),
            item(3, 4, 3, seasonal_top3_share=.9, active_months=8,
                 days_since_last_purchase=60, sales_trend_percent=-60, repeat_purchase_rate=.01),
            item(4, 1, 1, days_since_last_purchase=45, sales_trend_percent=-50,
                 repeat_purchase_rate=.01, profit_percent=5, wastage_percent=25),
        ]
        rows += [item(10 + index, 100 + index, 70 + index) for index in range(8)]
        result = analyze_slow_moving(pd.DataFrame(rows)).set_index("Item_ID")
        self.assertEqual(result.loc[1, "Slow_Moving_Status"], "HIDDEN_OPPORTUNITY")
        self.assertEqual(result.loc[2, "Slow_Moving_Status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result.loc[2, "History_Status"], "INSUFFICIENT")
        self.assertEqual(result.loc[3, "Slow_Moving_Status"], "SEASONAL_REVIEW")
        self.assertEqual(result.loc[4, "Slow_Moving_Status"], "SLOW_MOVER")
        self.assertEqual(result.loc[4, "Severity"], "HIGH")
        self.assertLess(result.loc[4, "Evidence"]["volume_percentile"], .35)
        self.assertIn("order frequency", result.loc[4, "Reason"])

    def test_same_item_can_be_slow_in_one_location_and_strong_in_another(self):
        rows = [item(99, 1, 1, Location_ID=1, days_since_last_purchase=50,
                     sales_trend_percent=-50, repeat_purchase_rate=.01),
                item(99, 1000, 500, Location_ID=2, days_since_last_purchase=1,
                     sales_trend_percent=20, repeat_purchase_rate=.3)]
        for location in (1, 2):
            rows += [item(200 + index, 100 + index, 70 + index, Location_ID=location)
                     for index in range(5)]
        result = analyze_slow_moving(pd.DataFrame(rows)).set_index(["Location_ID", "Item_ID"])
        self.assertEqual(result.loc[(1, 99), "Slow_Moving_Status"], "SLOW_MOVER")
        self.assertEqual(result.loc[(2, 99), "Slow_Moving_Status"], "NOT_SLOW")
        self.assertEqual(result.loc[(1, 99), "Evidence"]["location_context"], "LOCATION_1")


if __name__ == "__main__":
    unittest.main()
