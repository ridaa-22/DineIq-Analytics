import csv
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spark_jobs.ingest import create_spark, load_table, IngestionError
from spark_jobs.schemas import SCHEMAS


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = create_spark("DineIQ-Ingestion-Tests")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dineiq-ingest-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, table="Order_Items", changes=None, name="input.csv", fields=None, rows=1):
        columns = fields or SCHEMAS[table].fieldNames()
        values = {}
        for field in SCHEMAS[table]:
            kind = field.dataType.simpleString()
            values[field.name] = "1" if kind == "bigint" else "10.00" if kind.startswith("decimal") else "2025-01-01" if kind == "date" else "2025-01-01T12:00:00+05:00" if kind == "timestamp" else "Test"
        values.update(Channel="Dine-in", Order_Status="Completed", Preferred_Channel="App", Reason="Overproduction")
        values.update(changes or {})
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for _ in range(rows):
                writer.writerow(values)
        return path

    def test_multifile_and_explicit_decimal_schema(self):
        paths = [self.file(name="a.csv"), self.file(name="b.csv", changes={"Order_Item_ID": "2"})]
        df, info = load_table(self.spark, "Order_Items", paths)
        self.assertEqual(info["rows"], 2)
        self.assertEqual(info["input_files"], 2)
        self.assertEqual(df.schema["Unit_Price"].dataType.simpleString(), "decimal(18,2)")
        df.unpersist()

    def test_missing_file_and_column(self):
        with self.assertRaisesRegex(IngestionError, "missing source"):
            load_table(self.spark, "Order_Items", [self.root / "absent.csv"])
        with self.assertRaisesRegex(IngestionError, "invalid columns"):
            load_table(self.spark, "Order_Items", [self.file(fields=["Order_Item_ID"])])

    def test_invalid_numeric_and_precision_stop(self):
        for field, value in [("Quantity", "not-a-number"), ("Quantity", "1.5"), ("Unit_Price", "10.001")]:
            with self.assertRaisesRegex(IngestionError, "invalid source types"):
                load_table(self.spark, "Order_Items", [self.file(changes={field: value})])

    def test_missing_required_id_and_bad_enum_stop(self):
        with self.assertRaisesRegex(IngestionError, "required IDs"):
            load_table(self.spark, "Order_Items", [self.file(changes={"Item_ID": ""})])
        with self.assertRaisesRegex(IngestionError, "unsupported enums"):
            load_table(self.spark, "Orders", [self.file("Orders", {"Order_Status": "Unknown"})])

    def test_invalid_nonempty_dates_stop(self):
        with self.assertRaisesRegex(IngestionError, "invalid source types"):
            load_table(self.spark, "Orders", [self.file("Orders", {"Order_DateTime": "2025-99-99"})])

    def test_dirty_numeric_values_and_missing_nonid_are_retained(self):
        df, _ = load_table(self.spark, "Order_Items", [self.file(changes={"Quantity": "-1"})])
        self.assertEqual(df.first().Quantity, -1)
        df.unpersist()
        df, _ = load_table(self.spark, "Orders", [self.file("Orders", {"Order_DateTime": "", "Promotion_ID": ""})])
        self.assertIsNone(df.first().Order_DateTime)
        df.unpersist()

    def test_empty_and_duplicate_input_files_stop(self):
        path = self.file(rows=0)
        with self.assertRaisesRegex(IngestionError, "no records"):
            load_table(self.spark, "Order_Items", [path])
        with self.assertRaisesRegex(IngestionError, "distinct input files"):
            load_table(self.spark, "Order_Items", [path, path])

    def test_malformed_record_and_differing_headers_stop(self):
        path = self.file()
        with path.open("a", encoding="utf-8") as target:
            target.write("1,2\n")
        with self.assertRaisesRegex(IngestionError, "malformed CSV record"):
            load_table(self.spark, "Order_Items", [path])
        a = self.file(name="a.csv")
        b = self.file(name="b.csv", fields=list(reversed(SCHEMAS["Order_Items"].fieldNames())))
        with self.assertRaisesRegex(IngestionError, "column order"):
            load_table(self.spark, "Order_Items", [a, b])


if __name__ == "__main__":
    unittest.main(verbosity=2)
