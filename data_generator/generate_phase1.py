"""Repair the legacy scale scaffold into versioned, reproducible synthetic raw data.

Standard library only. Never overwrites an output directory or edits legacy data.
This is a data generator, not cleaning, Spark processing, or a predictive model.
"""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
START = date(2025, 1, 1)
END = date(2026, 1, 1)
TZ = timezone(timedelta(hours=5))


def read(path):
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def money(value):
    return f"{value // 100}.{value % 100:02d}"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def write(path, rows):
    iterator = iter(rows)
    first = next(iterator)
    with path.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(first), lineterminator="\n")
        writer.writeheader()
        writer.writerow(first)
        count = 1
        for row in iterator:
            writer.writerow(row)
            count += 1
    return count


def unique(rows, key):
    # First occurrence wins only when taking the legacy generator scaffold.
    # No legacy file is cleaned or overwritten by this operation.
    result = {}
    for row in rows:
        result.setdefault(int(row[key]), dict(row))
    return result


def generate(output, seed=42):
    output = Path(output).resolve()
    legacy = ROOT / "Dineiq_Dataset_RM"
    if output.exists():
        raise ValueError(f"Output already exists; choose a new version: {output}")
    if output == legacy or legacy in output.parents or output in legacy.parents:
        raise ValueError("Output must be separate from the preserved legacy dataset")
    source_hashes = {p.name: digest(p) for p in sorted(legacy.iterdir()) if p.is_file()}
    customers = unique(read(legacy / "Customers.csv"), "Customer_ID")
    menu = unique(read(legacy / "Menu_Items.csv"), "Item_ID")
    locations = unique(read(legacy / "Restaurants.csv"), "Location_ID")
    categories = read(legacy / "Menu_Categories.csv")
    old_orders = unique(read(legacy / "Orders.csv"), "Order_ID")
    if (len(customers), len(menu), len(locations), len(categories), len(old_orders)) != (50000, 150, 20, 10, 100000):
        raise ValueError("Legacy scaffold must contain 50K customers, 150 items, 20 locations, 10 categories, 100K orders")
    rng = random.Random(seed)
    costs = {i: cents(r["Cost"]) for i, r in menu.items()}
    prices = {i: max(cents(r["Base_Price"]), costs[i] * 2) for i, r in menu.items()}
    overrides = {1: (1050, 1000), 2: (200, 1200), 3: (300, 850), 4: (650, 900),
                 6: (350, 1000), 10: (650, 660), 11: (300, 850), 14: (250, 1000)}
    for i, (cost, price) in overrides.items():
        costs[i], prices[i] = cost * 100, price * 100
    for i, row in menu.items():
        row.update(Cost=money(costs[i]), Base_Price=money(prices[i]), Is_Available="1",
                   Introduced_Date="2025-12-01" if i == 9 else "2025-01-01")
    for i, row in customers.items():
        row["Signup_Date"] = "2025-12-01" if i >= 49001 else min(row["Signup_Date"], "2025-01-01")
    for row in locations.values():
        row["Opening_Date"] = min(row["Opening_Date"], "2025-01-01")

    promotions = []
    for i in range(1, 21):
        item = {1: 4, 2: 1, 3: 12}.get(i, 15 + i)
        month = 6 if i == 1 else 1 if i in (2, 3) else 1 + ((i - 4) % 4) * 3
        start = date(2025, month, 1)
        end = date(2025, 6, 30) if i == 1 else date(2025, 12, 31) if i in (2, 3) else min(start + timedelta(days=60), END)
        promotions.append({"Promotion_ID": str(i), "Promotion_Name": f"Campaign {i}",
                           "Discount_Percent": str(40 if i == 1 else 35 if i == 2 else 20),
                           "Start_Date": start.isoformat(), "End_Date": end.isoformat(),
                           "Applicable_Category_ID": menu[item]["Category_ID"], "Applicable_Item_ID": str(item)})
    promos = {int(r["Promotion_ID"]): r for r in promotions}
    days = [START + timedelta(days=n) for n in range((END - START).days)]
    day_weights = [(1.5 if d.weekday() >= 5 else 1) * (1.5 if d.month in (1, 12) else 1) for d in days]
    orders = {}
    active_promos = {d: [i for i, r in promos.items() if r["Start_Date"] <= d.isoformat() <= r["End_Date"]] for d in days}
    for i in sorted(old_orders):
        d = rng.choices(days, weights=day_weights)[0]
        customer = i if i <= 50000 else rng.randint(1, 1000) if rng.random() < .45 else rng.randint(2001, 48999)
        if 1001 <= customer <= 2000:
            d = START + timedelta(days=rng.randrange(181))
        elif customer >= 49001:
            d = date(2025, 12, 1) + timedelta(days=rng.randrange(31))
        if i == 1:
            d = START
        if i == 100000:
            d = END
        hour = rng.choices(list(range(24)), weights=[8 if h in (12, 13, 19, 20) else 1 for h in range(24)])[0]
        dt = datetime.combine(d, datetime.min.time(), TZ) + timedelta(hours=hour, minutes=rng.randrange(60))
        if i in (1, 100000):
            dt = datetime.combine(d, datetime.min.time(), TZ)
        candidates = active_promos.get(d, [])
        campaign = rng.choice(candidates) if candidates and rng.random() < .35 else None
        orders[i] = {"Order_ID": str(i), "Customer_ID": str(customer), "Location_ID": str(rng.randint(1, 20)),
                     "Order_DateTime": dt.isoformat(), "Channel": rng.choice(["Dine-in", "Takeaway", "Website", "App", "Third-Party Delivery"]),
                     "Promotion_ID": str(campaign) if campaign else "", "Order_Status": "Completed" if i in (1, 100000) or rng.random() < .96 else "Cancelled"}

    pricing = []
    for i in sorted(menu):
        for when in (START, date(2025, 7, 1)):
            price = prices[i] * 140 // 100 if i == 6 and when.month == 7 else prices[i]
            pricing.append({"Pricing_ID": str(len(pricing) + 1), "Item_ID": str(i), "Price": money(price), "Effective_Date": when.isoformat()})
    output.mkdir(parents=True, exist_ok=False)
    counts = {}
    injections = []

    def inject(rows, entity, key, field, value, count, rule):
        for row in rng.sample(rows, count):
            injections.append({"Entity": entity, "Record_ID": row[key], "Field": field,
                               "Rule": rule, "Original_Value": row[field], "Injected_Value": value})
            row[field] = value

    baskets = defaultdict(set)
    sold = Counter()
    seen_order = set()
    cdfs = {}
    negative_lines = set(rng.sample(range(1, 1000001), 150))

    def lines():
        with (legacy / "Order_Items.csv").open(encoding="utf-8", newline="") as source:
            for old in csv.DictReader(source):
                line_id, order_id = int(old["Order_Item_ID"]), int(old["Order_ID"])
                order = orders[order_id]
                d = date.fromisoformat(order["Order_DateTime"][:10])
                loc = int(order["Location_ID"])
                campaign = promos.get(int(order["Promotion_ID"])) if order["Promotion_ID"] else None
                promo_item = int(campaign["Applicable_Item_ID"]) if campaign else 0
                key = (1 if loc == 1 else 2 if loc == 2 else 0, d.month, d.weekday() >= 5, promo_item, d == date(2025, 8, 15), d >= date(2025, 12, 1))
                if key not in cdfs:
                    weights = [1.] * 150
                    for item, weight in {1: 18, 2: .03, 3: 12, 4: 35 if promo_item == 4 else .5,
                                         5: 20 if loc == 1 else .02 if loc == 2 else 1,
                                         6: 10 if d < date(2025, 7, 1) else 1,
                                         7: 14 if d.weekday() >= 5 else .02,
                                         8: 15 if d.month in (1, 12) else .02,
                                         9: 2 if d >= date(2025, 12, 1) else 0,
                                         10: 3, 11: 12, 12: 25 if promo_item == 12 else .03,
                                         13: 180 if d == date(2025, 8, 15) else .3, 14: 4}.items():
                        weights[item - 1] = weight
                    total = 0
                    cumulative = []
                    for weight in weights:
                        total += weight
                        cumulative.append(total)
                    cdfs[key] = cumulative
                cumulative = cdfs[key]
                item = promo_item if order_id not in seen_order and promo_item else bisect_left(cumulative, rng.random() * cumulative[-1]) + 1
                seen_order.add(order_id)
                quantity = rng.choices([1, 2, 3], weights=[70, 22, 8])[0]
                price = prices[item] * 140 // 100 if item == 6 and d >= date(2025, 7, 1) else prices[item]
                rate = int(campaign["Discount_Percent"]) if campaign and item == promo_item else 0
                discount = (price * quantity * rate + 50) // 100
                row = {"Order_Item_ID": str(line_id), "Order_ID": str(order_id), "Item_ID": str(item),
                       "Quantity": str(quantity), "Unit_Price": money(price), "Discount_Applied": money(discount)}
                baskets[order_id].add(item)
                if order["Order_Status"] == "Completed":
                    sold[(d.isoformat(), item, loc)] += quantity
                if line_id in negative_lines:
                    injections.append({"Entity": "Order_Items", "Record_ID": str(line_id), "Field": "Quantity", "Rule": "NEGATIVE_QUANTITY",
                                       "Original_Value": str(quantity), "Injected_Value": "-1"})
                    row["Quantity"] = "-1"
                yield row

    counts["Order_Items"] = write(output / "Order_Items.csv", lines())
    if counts["Order_Items"] != 1000000:
        raise ValueError("Expected exactly 1,000,000 legacy line IDs")
    completed = [i for i, r in orders.items() if r["Order_Status"] == "Completed"]
    ratings = []
    for i in range(1, 100001):
        order_id = rng.choice(completed)
        item = rng.choice(sorted(baskets[order_id]))
        order = orders[order_id]
        dt = datetime.fromisoformat(order["Order_DateTime"]) + timedelta(hours=rng.randint(1, 48))
        stars = 5 if item == 10 else rng.choice([1, 2]) if item == 11 else rng.choices([1, 2, 3, 4, 5], weights=[3, 5, 12, 35, 45])[0]
        if item == 13 and order["Order_DateTime"].startswith("2025-08-15"):
            stars, dt = 5, datetime(2025, 8, 18, 12, tzinfo=TZ)
        ratings.append({"Rating_ID": str(i), "Order_ID": str(order_id), "Item_ID": str(item), "Customer_ID": order["Customer_ID"], "Stars": str(stars), "Rating_Date": dt.isoformat()})

    keys = sorted(sold)
    high_waste_keys = [key for key in keys if key[1] == 3]
    other_keys = [key for key in keys if key[1] != 3]
    selected = sorted(high_waste_keys + rng.sample(other_keys, 50000 - len(high_waste_keys)))
    wastage = []
    wasted_by_pair = Counter()
    for i, (d, item, loc) in enumerate(selected, 1):
        demand = sold[(d, item, loc)]
        wasted = max(1, round(demand * (.7 if item == 3 else .4 if item == 4 and d.startswith("2025-06") else .03)))
        wasted_by_pair[(item, loc)] += wasted
        wastage.append({"Wastage_ID": str(i), "Item_ID": str(item), "Location_ID": str(loc), "Wastage_Date": d,
                        "Quantity_Wasted": str(wasted), "Cost_Impact": money(wasted * costs[item]), "Reason": "Overproduction",
                        "Demand_Quantity": str(demand), "Prepared_Quantity": str(demand + wasted), "Quantity_Consumed": str(demand)})
    consumed = Counter()
    for (_, item, loc), quantity in sold.items():
        consumed[(item, loc)] += quantity
    inventory = read(legacy / "Inventory.csv")
    pairs = {(int(r["Item_ID"]), int(r["Location_ID"])) for r in inventory}
    for loc in range(1, 21):
        for item in range(1, 151):
            if (item, loc) not in pairs:
                inventory.append({"Inventory_ID": str(len(inventory) + 1), "Location_ID": str(loc), "Item_ID": str(item), "Stock_Quantity": "0", "Reorder_Level": "20", "Last_Restocked_Date": "2026-01-01"})
    for row in inventory:
        pair = (int(row["Item_ID"]), int(row["Location_ID"]))
        row.update(Stock_Quantity="100", Last_Restocked_Date="2026-01-01", Opening_Stock="100",
                   Received_Quantity=str(consumed[pair] + wasted_by_pair[pair]), Consumed_Quantity=str(consumed[pair]),
                   Wasted_Quantity=str(wasted_by_pair[pair]), Period_Start="2025-01-01", Period_End="2026-01-01")

    customer_rows = [customers[i] for i in sorted(customers)]
    order_rows = [orders[i] for i in sorted(orders)]
    # Known defects are a separate generator fixture, never undocumented business contradictions.
    inject(customer_rows, "Customers", "Customer_ID", "Customer_Name", "", 120, "MISSING_NAME")
    eligible_dates = [r for r in order_rows if int(r["Order_ID"]) not in (1, 100000)]
    inject(eligible_dates, "Orders", "Order_ID", "Order_DateTime", "", 30, "MISSING_DATE")
    inject(list(menu.values()), "Menu_Items", "Item_ID", "Base_Price", "-1.00", 5, "INVALID_BASE_PRICE")
    inject(ratings, "Ratings", "Rating_ID", "Stars", "8", 60, "INVALID_STARS")
    inject(wastage, "Wastage", "Wastage_ID", "Quantity_Wasted", "-5", 40, "NEGATIVE_WASTAGE")
    for entity, rows, key, count in [("Customers", customer_rows, "Customer_ID", 40), ("Orders", order_rows, "Order_ID", 80)]:
        extras = [dict(r) for r in rng.sample(rows, count)]
        for row in extras:
            injections.append({"Entity": entity, "Record_ID": row[key], "Field": "*", "Rule": "DUPLICATE_ROW", "Original_Value": "1", "Injected_Value": "2"})
        rows.extend(extras)
    for name, rows in [("Customers", customer_rows), ("Orders", order_rows), ("Menu_Items", [menu[i] for i in sorted(menu)]),
                       ("Menu_Categories", categories), ("Restaurants", [locations[i] for i in sorted(locations)]),
                       ("Promotions", promotions), ("Pricing_History", pricing), ("Ratings", ratings), ("Inventory", inventory), ("Wastage", wastage)]:
        counts[name] = write(output / f"{name}.csv", rows)
    write(output / "injected_defects.csv", sorted(injections, key=lambda r: (r["Entity"], int(r["Record_ID"]), r["Field"])))
    files = {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in sorted(output.glob("*.csv"))}
    manifest = {"dataset_version": "phase1-v1", "seed": seed, "currency": "PKR", "timezone": "Asia/Karachi",
                "transaction_start": "2025-01-01T00:00:00+05:00", "transaction_end": "2026-01-01T00:00:00+05:00",
                "end_inclusive": True, "source_snapshot": "legacy-rm-phase0", "source_sha256": source_hashes,
                "generator_sha256": digest(Path(__file__)), "counts": counts, "files": files,
                "injected_defect_count": len(injections), "storage": "raw CSV; no cleaned/processed Parquet claim"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if source_hashes != {p.name: digest(p) for p in sorted(legacy.iterdir()) if p.is_file()}:
        raise RuntimeError("Legacy source changed during generation")
    print(json.dumps({"output": str(output), "counts": counts, "injected_defects": len(injections)}, indent=2), flush=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/raw/phase1-v1")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        generate(args.output, args.seed)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Generation failed: {exc}\n")
