"""Relationship and ID checks for the controlled scale fixture."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.make_scale_fixture import replicate


class ScaleFixtureTests(unittest.TestCase):
    def test_replicated_orders_and_lines_keep_references_and_unique_line_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            orders = root / "orders.csv"
            lines = root / "lines.csv"
            orders.write_text("Order_ID,Customer_ID\n1,7\n2,8\n", encoding="utf-8")
            lines.write_text("Order_Item_ID,Order_ID,Item_ID\n1,1,4\n2,2,5\n", encoding="utf-8")
            self.assertEqual(replicate(orders, root / "scaled_orders.csv", 5, "Order_ID"), 10)
            self.assertEqual(replicate(lines, root / "scaled_lines.csv", 5,
                                       "Order_Item_ID", "Order_ID"), 10)
            def read(path):
                with path.open(newline="", encoding="utf-8") as source:
                    return list(csv.DictReader(source))
            result_orders = read(root / "scaled_orders.csv")
            result_lines = read(root / "scaled_lines.csv")
            order_ids = {row["Order_ID"] for row in result_orders}
            self.assertEqual(len(order_ids), 10)
            self.assertEqual(len({row["Order_Item_ID"] for row in result_lines}), 10)
            self.assertTrue(all(row["Order_ID"] in order_ids for row in result_lines))
            self.assertEqual({row["Item_ID"] for row in result_lines}, {"4", "5"})


if __name__ == "__main__":
    unittest.main()
