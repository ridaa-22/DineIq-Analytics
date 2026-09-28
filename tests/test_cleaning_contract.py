"""Reject hidden invalid raw records with reviewable evidence."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from Python_Pipeline import build_processed as cleaner


class CleaningContractTests(unittest.TestCase):
    def test_nonfinite_financial_channel_quantity_and_balance_are_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            original_read = cleaner.read

            def injected(name):
                frame = original_read(name)
                if name == "Orders":
                    frame.loc[frame.index[0], "Channel"] = "Unknown channel"
                elif name == "Order_Items":
                    frame.loc[frame.index[0], "Unit_Price"] = float("inf")
                    frame.loc[frame.index[1], "Quantity"] = 1.5
                elif name == "Wastage":
                    frame.loc[frame.index[0], "Quantity_Consumed"] = (
                        float(frame.loc[frame.index[0], "Prepared_Quantity"]) + 1)
                return frame

            with patch.object(cleaner, "OUT", Path(folder)), patch.object(cleaner, "read", side_effect=injected):
                cleaner.build()
            evidence = [json.loads(line) for line in (Path(folder) / "rejections.jsonl").read_text().splitlines()]
            rules = {row["rule"] for row in evidence}
            self.assertTrue({"known_channel", "finite_Unit_Price", "integer_quantity",
                             "preparation_balance"}.issubset(rules))
            sales = pd.read_parquet(Path(folder) / "sales.parquet")
            self.assertNotIn(1, sales.Order_Item_ID.values)
            self.assertNotIn(2, sales.Order_Item_ID.values)
