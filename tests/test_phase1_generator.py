"""Phase 1 generator acceptance checks; no Spark or downstream cleaning pipeline."""
import csv
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data_generator"))
from generate_phase1 import cents, digest, generate


def records(path):
    with path.open(encoding="utf-8", newline="") as source:
        yield from csv.DictReader(source)


def check(dataset):
    manifest = json.loads((dataset / "manifest.json").read_text())
    for name, metadata in manifest["files"].items():
        assert digest(dataset / name) == metadata["sha256"], name
    defects = list(records(dataset / "injected_defects.csv"))
    originals = {(r["Entity"], r["Record_ID"], r["Field"]): r["Original_Value"] for r in defects if r["Field"] != "*"}
    def restored(entity, row):
        row = dict(row)
        pk = next(iter(row))
        for field in row:
            row[field] = originals.get((entity, row[pk], field), row[field])
        return row
    tables = {}
    for entity in manifest["counts"]:
        if entity == "Order_Items":
            continue
        rows = list(records(dataset / f"{entity}.csv"))
        assert len(rows) == manifest["counts"][entity], entity
        tables[entity] = {int(next(iter(r.values()))): restored(entity, r) for r in rows}
    assert {k: len(tables[k]) for k in ("Customers", "Orders", "Menu_Items", "Menu_Categories", "Restaurants", "Ratings", "Wastage")} == {
        "Customers": 50000, "Orders": 100000, "Menu_Items": 150, "Menu_Categories": 10,
        "Restaurants": 20, "Ratings": 100000, "Wastage": 50000}
    orders, menu, promos = tables["Orders"], tables["Menu_Items"], tables["Promotions"]
    timestamps = []
    baskets = defaultdict(set)
    units, margin, group_units, group_margin, daily = Counter(), Counter(), Counter(), Counter(), Counter()
    for i, r in orders.items():
        dt = datetime.fromisoformat(r["Order_DateTime"])
        assert dt.utcoffset().total_seconds() == 18000
        timestamps.append(dt)
        assert date.fromisoformat(tables["Customers"][int(r["Customer_ID"])]["Signup_Date"]) <= dt.date()
        assert date.fromisoformat(tables["Restaurants"][int(r["Location_ID"])]["Opening_Date"]) <= dt.date()
        assert r["Order_Status"] in ("Completed", "Cancelled")
        if r["Promotion_ID"]:
            p = promos[int(r["Promotion_ID"])]
            assert p["Start_Date"] <= dt.date().isoformat() <= p["End_Date"]
    assert min(timestamps).isoformat() == "2025-01-01T00:00:00+05:00"
    assert max(timestamps).isoformat() == "2026-01-01T00:00:00+05:00"
    count = 0
    for raw in records(dataset / "Order_Items.csv"):
        count += 1
        assert int(raw["Order_Item_ID"]) == count
        r = restored("Order_Items", raw)
        oid, item, q = int(r["Order_ID"]), int(r["Item_ID"]), int(r["Quantity"])
        order = orders[oid]
        d = date.fromisoformat(order["Order_DateTime"][:10])
        loc = int(order["Location_ID"])
        assert q > 0 and item in menu
        assert d.isoformat() >= menu[item]["Introduced_Date"]
        price = cents(menu[item]["Base_Price"])
        if item == 6 and d >= date(2025, 7, 1):
            price = price * 140 // 100
        assert cents(r["Unit_Price"]) == price
        campaign = promos[int(order["Promotion_ID"])] if order["Promotion_ID"] else None
        eligible = campaign and item == int(campaign["Applicable_Item_ID"])
        if eligible:
            assert menu[item]["Category_ID"] == campaign["Applicable_Category_ID"]
        expected_discount = (price * q * int(campaign["Discount_Percent"]) + 50) // 100 if eligible else 0
        assert cents(r["Discount_Applied"]) == expected_discount
        baskets[oid].add(item)
        if order["Order_Status"] != "Completed":
            continue
        profit = price * q - expected_discount - cents(menu[item]["Cost"]) * q
        units[item] += q
        margin[item] += profit
        daily[(d.isoformat(), item, loc)] += q
        for group in (f"month:{d.month}", f"loc:{loc}", f"weekend:{d.weekday() >= 5}", f"promo:{bool(eligible)}"):
            group_units[(item, group)] += q
            group_margin[(item, group)] += profit
    assert count == 1000000
    for oid, r in orders.items():
        if r["Promotion_ID"]:
            assert int(promos[int(r["Promotion_ID"])]["Applicable_Item_ID"]) in baskets[oid]
    rating_totals, rating_count = Counter(), Counter()
    burst = Counter()
    for r in tables["Ratings"].values():
        oid, item = int(r["Order_ID"]), int(r["Item_ID"])
        assert item in baskets[oid]
        assert orders[oid]["Order_Status"] == "Completed"
        assert r["Customer_ID"] == orders[oid]["Customer_ID"]
        assert datetime.fromisoformat(r["Rating_Date"]) >= datetime.fromisoformat(orders[oid]["Order_DateTime"])
        assert 1 <= int(r["Stars"]) <= 5
        rating_totals[item] += int(r["Stars"])
        rating_count[item] += 1
        if item == 13:
            burst[r["Rating_Date"]] += 1
    waste = Counter()
    for r in tables["Wastage"].values():
        item, loc = int(r["Item_ID"]), int(r["Location_ID"])
        q = int(r["Quantity_Wasted"])
        demand = daily[(r["Wastage_Date"], item, loc)]
        assert demand == int(r["Demand_Quantity"]) == int(r["Quantity_Consumed"])
        assert int(r["Prepared_Quantity"]) == demand + q
        assert cents(r["Cost_Impact"]) == q * cents(menu[item]["Cost"])
        waste[item] += q
    # daily uses restored original quantities; injected errors are fixture-only.
    totals = Counter()
    for (_, item, loc), q in daily.items():
        totals[(item, loc)] += q
    for r in tables["Inventory"].values():
        pair = (int(r["Item_ID"]), int(r["Location_ID"]))
        assert int(r["Consumed_Quantity"]) == totals[pair]
        assert int(r["Opening_Stock"]) + int(r["Received_Quantity"]) - int(r["Consumed_Quantity"]) - int(r["Wasted_Quantity"]) == int(r["Stock_Quantity"])
    assert units[1] > statistics.median(units.values()) * 5 and margin[1] < 0
    assert units[2] < statistics.median(units.values()) / 10 and margin[2] > 0
    assert waste[3] / units[3] > .5
    assert group_units[(4, "month:6")] > group_units[(4, "month:5")] * 3
    assert group_margin[(4, "month:6")] < 0
    assert group_units[(5, "loc:1")] > group_units[(5, "loc:2")] * 20
    assert sum(group_units[(6, f"month:{m}")] for m in range(1, 7)) > sum(group_units[(6, f"month:{m}")] for m in range(7, 13)) * 3
    assert group_units[(7, "weekend:True")] > group_units[(7, "weekend:False")] * 10
    assert group_units[(8, "month:1")] + group_units[(8, "month:12")] > sum(group_units[(8, f"month:{m}")] for m in range(2, 12)) * 10
    assert rating_totals[10] / rating_count[10] > 4.5 and margin[10] / units[10] < 2000
    assert rating_totals[11] / rating_count[11] < 2.1 and units[11] > statistics.median(units.values()) * 3
    assert group_units[(12, "promo:True")] > group_units[(12, "promo:False")] * 3
    assert max(burst.values()) >= 10
    assert all(r["Order_DateTime"][:10] <= "2025-06-30" for r in orders.values() if 1001 <= int(r["Customer_ID"]) <= 2000)
    expected_defects = {"NEGATIVE_QUANTITY": 150, "MISSING_NAME": 120, "MISSING_DATE": 30,
                        "INVALID_BASE_PRICE": 5, "INVALID_STARS": 60, "NEGATIVE_WASTAGE": 40, "DUPLICATE_ROW": 120}
    assert dict(Counter(r["Rule"] for r in defects)) == expected_defects
    return {"status": "PASS", "counts": manifest["counts"], "generator_fixture_assertions": "relationships, time bounds, economics, operational balances, scenarios, declared defects",
            "scenario_measurements": {"loss_item_units": units[1], "loss_item_margin_pkr": margin[1] / 100,
                                      "hidden_item_units": units[2], "high_waste_ratio": waste[3] / units[3],
                                      "harmful_promo_june_margin_pkr": group_margin[(4, "month:6")] / 100,
                                      "rating_burst_count": max(burst.values())}}


class GeneratorChecks(unittest.TestCase):
    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generate(Path(directory))

    def test_preserved_source_is_refused(self):
        with self.assertRaises(ValueError):
            generate(ROOT / "Dineiq_Dataset_RM")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dataset":
        result = check(Path(sys.argv[2]).resolve())
        print(json.dumps(result, indent=2))
    else:
        unittest.main()
