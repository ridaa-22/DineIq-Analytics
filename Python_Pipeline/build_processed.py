"""Create reproducible, cleaned analytical Parquet and business aggregates.

Run from the repository root: python -m Python_Pipeline.build_processed
"""

import json
import hashlib
import numpy as np
from pathlib import Path

import pandas as pd
from Python_Pipeline.business_time import local_dates, parse_order_timestamps


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "phase1-v1"
OUT = ROOT / "data" / "processed" / "phase1-v1"
PARQUET_OPTIONS = {"engine": "pyarrow", "coerce_timestamps": "us", "allow_truncated_timestamps": True}
SPARK_SNAPSHOT_NAMES = ("orders_validated", "customers_validated", "order_items_validated",
    "menu_items_validated", "menu_categories_validated", "restaurant_locations_validated",
    "promotions_validated", "pricing_history_validated", "ratings", "inventory_validated",
    "wastage", "sales")


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def read(name):
    return pd.read_csv(RAW / f"{name}.csv", low_memory=False)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    orders = read("Orders")
    lines = read("Order_Items")
    menu = read("Menu_Items")
    price_history = read("Pricing_History")
    customers = read("Customers")
    locations = read("Restaurants")
    ratings = read("Ratings")
    wastage = read("Wastage")
    rejections = []

    def reject(table, frame, identifier, rule, mask, reason):
        for value in frame.loc[mask.fillna(True), identifier]:
            rejections.append({"record_identifier": str(value), "source_table": table,
                               "rule": rule, "reason": reason, "action": "quarantined"})

    def finite(series):
        return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).notna()

    valid_channels = {"Dine-in", "Takeaway", "Website", "Third-Party Delivery", "App"}
    reject("Orders", orders, "Order_ID", "known_channel", ~orders.Channel.isin(valid_channels), "Unknown ordering channel")
    orders = orders[orders.Channel.isin(valid_channels)]
    for field in ("Quantity", "Unit_Price", "Discount_Applied"):
        bad = ~finite(lines[field])
        reject("Order_Items", lines, "Order_Item_ID", f"finite_{field}", bad, "Nonfinite financial or quantity value")
        lines = lines[~bad]
    fractional = pd.to_numeric(lines.Quantity, errors="coerce").mod(1).ne(0)
    reject("Order_Items", lines, "Order_Item_ID", "integer_quantity", fractional, "Quantity must be whole portions")
    lines = lines[~fractional]
    for field in ("Base_Price", "Cost"):
        bad = ~finite(menu[field])
        reject("Menu_Items", menu, "Item_ID", f"finite_{field}", bad, "Nonfinite menu financial value")
        menu = menu[~bad]
    bad = ~finite(price_history.Price)
    reject("Pricing_History", price_history, "Pricing_ID", "finite_price", bad, "Nonfinite price")
    price_history = price_history[~bad]
    for field in ("Quantity_Wasted", "Cost_Impact", "Demand_Quantity", "Prepared_Quantity", "Quantity_Consumed"):
        bad = ~finite(wastage[field])
        reject("Wastage", wastage, "Wastage_ID", f"finite_{field}", bad, "Nonfinite wastage value")
        wastage = wastage[~bad]
    bad = (pd.to_numeric(wastage.Quantity_Consumed) + pd.to_numeric(wastage.Quantity_Wasted)
           > pd.to_numeric(wastage.Prepared_Quantity))
    reject("Wastage", wastage, "Wastage_ID", "preparation_balance", bad, "Consumed plus wasted exceeds prepared")
    wastage = wastage[~bad]
    counts = {"dataset_version": "phase1-v1-clean-v3", "raw_orders": len(orders), "raw_lines": len(lines)}
    line_qty = pd.to_numeric(lines.Quantity, errors="coerce")
    line_price = pd.to_numeric(lines.Unit_Price, errors="coerce")
    line_discount = pd.to_numeric(lines.Discount_Applied, errors="coerce")
    waste_qty = pd.to_numeric(wastage.Quantity_Wasted, errors="coerce")
    waste_cost = pd.to_numeric(wastage.Cost_Impact, errors="coerce")
    counts["detected_conditions"] = {
        "duplicate_order_headers": int(orders.Order_ID.duplicated().sum()),
        "duplicate_customers": int(customers.Customer_ID.duplicated().sum()),
        "missing_customer_names": int(customers.Customer_Name.isna().sum()),
        "missing_order_dates": int(orders.Order_DateTime.isna().sum()),
        "missing_order_ids": int(orders.Order_ID.isna().sum()),
        "invalid_order_statuses": int((~orders.Order_Status.isin(["Completed", "Cancelled"])).sum()),
        "cancelled_orders": int(orders.Order_Status.eq("Cancelled").sum()),
        "duplicate_order_lines": int(lines.Order_Item_ID.duplicated().sum()),
        "invalid_line_quantities": int((~line_qty.gt(0)).sum()),
        "invalid_line_prices": int((~line_price.gt(0)).sum()),
        "invalid_line_discounts": int((~line_discount.ge(0) | line_discount.gt(line_qty * line_price)).sum()),
        "line_unknown_order_ids": int((~lines.Order_ID.isin(orders.Order_ID)).sum()),
        "line_unknown_item_ids": int((~lines.Item_ID.isin(menu.Item_ID)).sum()),
        "invalid_base_prices": int((~pd.to_numeric(menu.Base_Price, errors="coerce").gt(0)).sum()),
        "invalid_history_prices": int((~pd.to_numeric(price_history.Price, errors="coerce").gt(0)).sum()),
        "invalid_rating_stars": int((~pd.to_numeric(ratings.Stars, errors="coerce").between(1, 5)).sum()),
        "rating_unknown_order_ids": int((~ratings.Order_ID.isin(orders.Order_ID)).sum()),
        "rating_unknown_item_ids": int((~ratings.Item_ID.isin(menu.Item_ID)).sum()),
        "invalid_wastage_quantities": int((~waste_qty.ge(0)).sum()),
        "invalid_wastage_costs": int((~waste_cost.ge(0)).sum()),
        "wastage_unknown_item_ids": int((~wastage.Item_ID.isin(menu.Item_ID)).sum()),
        "wastage_unknown_location_ids": int((~wastage.Location_ID.isin(locations.Location_ID)).sum()),
    }

    orders["Order_DateTime"] = parse_order_timestamps(orders["Order_DateTime"])
    bad = orders.Order_ID.isna() | orders.Customer_ID.isna() | orders.Location_ID.isna() | orders.Order_DateTime.isna()
    reject("Orders", orders, "Order_ID", "required_order_fields", bad, "Missing ID or invalid timestamp")
    orders = orders.drop_duplicates("Order_ID", keep="first")
    orders = orders[orders.Order_ID.notna() & orders.Customer_ID.notna() & orders.Location_ID.notna()
                    & orders.Order_DateTime.notna()]
    bad = ~orders.Customer_ID.isin(customers.Customer_ID) | ~orders.Location_ID.isin(locations.Location_ID)
    reject("Orders", orders, "Order_ID", "known_order_references", bad, "Unknown customer or location")
    orders = orders[~bad]
    customers.drop_duplicates("Customer_ID").to_parquet(OUT / "customers_validated.parquet", index=False, **PARQUET_OPTIONS)
    locations.drop_duplicates("Location_ID").to_parquet(OUT / "restaurant_locations_validated.parquet", index=False, **PARQUET_OPTIONS)
    read("Menu_Categories").drop_duplicates("Category_ID").to_parquet(
        OUT / "menu_categories_validated.parquet", index=False, **PARQUET_OPTIONS)
    counts["valid_orders_all_statuses"] = len(orders)
    completed = orders[orders.Order_Status.eq("Completed")].copy()
    counts["completed_orders"] = len(completed)

    menu["Base_Price"] = pd.to_numeric(menu.Base_Price, errors="coerce")
    menu["Cost"] = pd.to_numeric(menu.Cost, errors="coerce")
    price_history["Price"] = pd.to_numeric(price_history.Price, errors="coerce")
    priced_items = price_history.loc[price_history.Price.gt(0), "Item_ID"]
    counts["invalid_base_price_items"] = int((~menu.Base_Price.gt(0)).sum())
    # Base_Price is a raw initial-list attribute; transaction Unit_Price is the
    # observed effective price. Keep an item when a valid price event exists.
    valid_menu = menu[menu.Cost.ge(0) & menu.Item_ID.isin(priced_items)].drop_duplicates("Item_ID")
    valid_menu.to_parquet(OUT / "menu_items_validated.parquet", index=False, **PARQUET_OPTIONS)
    price_history[price_history.Price.gt(0) & price_history.Item_ID.isin(valid_menu.Item_ID)].drop_duplicates(
        "Pricing_ID").to_parquet(OUT / "pricing_history_validated.parquet", index=False, **PARQUET_OPTIONS)
    promotions = read("Promotions").drop_duplicates("Promotion_ID")
    promotions = promotions[promotions.Applicable_Item_ID.isin(valid_menu.Item_ID) &
                            promotions.Applicable_Category_ID.isin(valid_menu.Category_ID)]
    promotions.to_parquet(OUT / "promotions_validated.parquet", index=False, **PARQUET_OPTIONS)
    inventory = read("Inventory").drop_duplicates("Inventory_ID")
    inventory = inventory[inventory.Item_ID.isin(valid_menu.Item_ID) &
                          inventory.Location_ID.isin(locations.Location_ID)]
    inventory.to_parquet(OUT / "inventory_validated.parquet", index=False, **PARQUET_OPTIONS)
    counts["valid_menu_items"] = len(valid_menu)
    for field in ("Quantity", "Unit_Price", "Discount_Applied"):
        lines[field] = pd.to_numeric(lines[field], errors="coerce")
    lines = lines.drop_duplicates("Order_Item_ID", keep="first")
    bad = (lines.Order_Item_ID.isna() | lines.Order_ID.isna() | lines.Item_ID.isna()
           | ~lines.Quantity.gt(0) | ~lines.Unit_Price.gt(0) | ~lines.Discount_Applied.ge(0)
           | ~lines.Discount_Applied.le(lines.Quantity * lines.Unit_Price))
    reject("Order_Items", lines, "Order_Item_ID", "valid_line_values", bad, "Missing reference or invalid quantity, price, or discount")
    lines = lines[lines.Order_Item_ID.notna() & lines.Order_ID.notna() & lines.Item_ID.notna()
                  & lines.Quantity.gt(0) & lines.Unit_Price.gt(0) & lines.Discount_Applied.ge(0)]
    lines = lines[lines.Discount_Applied.le(lines.Quantity * lines.Unit_Price)]
    bad = ~lines.Item_ID.isin(valid_menu.Item_ID) | ~lines.Order_ID.isin(orders.Order_ID)
    reject("Order_Items", lines, "Order_Item_ID", "known_line_references", bad, "Unknown order or valid item")
    lines = lines[~bad]
    lines.to_parquet(OUT / "order_items_validated.parquet", index=False, **PARQUET_OPTIONS)
    sales = lines.merge(completed, on="Order_ID", how="inner", validate="many_to_one")
    sales = sales.merge(valid_menu[["Item_ID", "Item_Name", "Category_ID", "Cost"]], on="Item_ID", validate="many_to_one")
    sales["Net_Revenue"] = sales.Quantity * sales.Unit_Price - sales.Discount_Applied
    sales["Cost_Total"] = sales.Quantity * sales.Cost
    sales["Contribution"] = sales.Net_Revenue - sales.Cost_Total
    sales["Date"] = local_dates(sales.Order_DateTime).astype(str)
    counts["clean_completed_lines"] = len(sales)
    sales.to_parquet(OUT / "sales.parquet", index=False, **PARQUET_OPTIONS)
    partitions = {}
    for location_id, subset in sales.groupby("Location_ID"):
        destination = OUT / "sales_by_location" / f"Location_ID={int(location_id)}"
        destination.mkdir(parents=True, exist_ok=True)
        subset.drop(columns="Location_ID").to_parquet(destination / "part.parquet", index=False, **PARQUET_OPTIONS)
        partitions[str(int(location_id))] = len(subset)
    counts["partitioned_sales_lines"] = sum(partitions.values())
    (OUT / "partition_strategy.json").write_text(json.dumps({
        "dataset": "sales_by_location", "partition_column": "Location_ID",
        "purpose": "Spark location pruning on clean completed sale lines",
        "rows_by_location": partitions}, indent=2), encoding="utf-8")
    orders.to_parquet(OUT / "orders_validated.parquet", index=False, **PARQUET_OPTIONS)

    item = sales.groupby("Item_ID").agg(Item_Name=("Item_Name", "first"), Category_ID=("Category_ID", "first"),
        Sales_Quantity=("Quantity", "sum"), Revenue=("Net_Revenue", "sum"), Cost=("Cost_Total", "sum"),
        Contribution=("Contribution", "sum"), Orders=("Order_ID", "nunique"),
        Customers=("Customer_ID", "nunique"), Discount=("Discount_Applied", "sum")).reset_index()
    item["Profit_Percent"] = (100 * item.Contribution / item.Revenue.where(item.Revenue.ne(0))).fillna(0)
    rating = ratings.copy()
    rating["Stars"] = pd.to_numeric(rating.Stars, errors="coerce")
    rating = rating.drop_duplicates("Rating_ID")
    bad = (~rating.Stars.between(1, 5) | ~rating.Order_ID.isin(completed.Order_ID)
           | ~rating.Item_ID.isin(valid_menu.Item_ID))
    reject("Ratings", rating, "Rating_ID", "valid_rating_references", bad, "Invalid stars, order, or item")
    rating = rating[rating.Stars.between(1, 5) & rating.Order_ID.isin(completed.Order_ID)
                    & rating.Item_ID.isin(valid_menu.Item_ID)]
    rating.to_parquet(OUT / "ratings.parquet", index=False, **PARQUET_OPTIONS)
    item = item.merge(rating.groupby("Item_ID").Stars.agg(["mean", "count"]).reset_index().rename(
        columns={"mean": "Average_Rating", "count": "Rating_Count"}), on="Item_ID", how="left")
    item.to_parquet(OUT / "menu_metrics.parquet", index=False, **PARQUET_OPTIONS)

    order_totals = sales.groupby(["Order_ID", "Customer_ID", "Location_ID"]).Net_Revenue.sum().reset_index()
    rfm = sales.groupby("Customer_ID").agg(Last_Order=("Order_DateTime", "max"),
        Frequency=("Order_ID", "nunique"), Monetary=("Net_Revenue", "sum"),
        Preferred_Location=("Location_ID", lambda x: x.mode().iloc[0])).reset_index()
    snapshot = sales.Order_DateTime.max() + pd.Timedelta(days=1)
    rfm["Recency_Days"] = (snapshot - rfm.Last_Order).dt.days
    rfm.to_parquet(OUT / "customer_rfm.parquet", index=False, **PARQUET_OPTIONS)
    order_totals.to_parquet(OUT / "order_totals.parquet", index=False, **PARQUET_OPTIONS)
    location_daily = sales.groupby(["Date", "Location_ID"]).agg(Demand=("Quantity", "sum"),
        Revenue=("Net_Revenue", "sum"), Contribution=("Contribution", "sum"),
        Orders=("Order_ID", "nunique")).reset_index()
    location_daily.to_parquet(OUT / "location_daily.parquet", index=False, **PARQUET_OPTIONS)

    for field in ("Quantity_Wasted", "Cost_Impact", "Demand_Quantity", "Prepared_Quantity", "Quantity_Consumed"):
        wastage[field] = pd.to_numeric(wastage[field], errors="coerce")
    wastage["Wastage_Date"] = pd.to_datetime(wastage.Wastage_Date, errors="coerce")
    wastage = wastage.drop_duplicates("Wastage_ID")
    bad = ~wastage.Item_ID.isin(valid_menu.Item_ID) | ~wastage.Location_ID.isin(locations.Location_ID)
    reject("Wastage", wastage, "Wastage_ID", "known_wastage_references", bad, "Unknown item or location")
    bad_values = (wastage.Wastage_Date.isna() | ~wastage.Quantity_Wasted.ge(0) | ~wastage.Cost_Impact.ge(0)
                  | ~wastage.Demand_Quantity.ge(0) | ~wastage.Prepared_Quantity.ge(0)
                  | ~wastage.Quantity_Consumed.ge(0) | ~wastage.Quantity_Wasted.le(wastage.Prepared_Quantity))
    reject("Wastage", wastage, "Wastage_ID", "valid_wastage_values", bad_values, "Invalid date or negative/impossible wastage value")
    wastage = wastage[wastage.Item_ID.isin(valid_menu.Item_ID) & wastage.Location_ID.isin(locations.Location_ID)
        & wastage.Wastage_Date.notna() & wastage.Quantity_Wasted.ge(0) & wastage.Cost_Impact.ge(0)
        & wastage.Demand_Quantity.ge(0) & wastage.Prepared_Quantity.ge(0) & wastage.Quantity_Consumed.ge(0)
        & wastage.Quantity_Wasted.le(wastage.Prepared_Quantity)]
    wastage.to_parquet(OUT / "wastage.parquet", index=False, **PARQUET_OPTIONS)
    counts["valid_wastage"] = len(wastage)
    counts["valid_ratings"] = len(rating)
    counts["quarantined_records"] = len(rejections)
    (OUT / "rejections.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rejections), encoding="utf-8")
    counts["cleaning_rules"] = {
        "orders": "First unique Order_ID; require IDs, valid timestamp, known customer/location; preserve cancelled headers but exclude from realized sales",
        "lines": "First unique Order_Item_ID; require IDs, positive quantity and unit price, nonnegative line discount no greater than gross; join to valid completed order and known priced item",
        "menu": "Require nonnegative cost and at least one positive effective price-history event; flag but do not substitute an invalid raw Base_Price",
        "ratings": "First unique Rating_ID; require 1-5 stars, completed order and known item",
        "wastage": "First unique Wastage_ID; require known item/location/date, nonnegative quantity/cost/demand/prepared/consumed and wasted no greater than prepared",
        "missing_customer_names": "Retain stable synthetic Customer_ID for analytics; do not impute a name",
        "partitioning": "Persist identical clean sales by Location_ID for Spark SQL; retain one-file Parquet for Python",
    }
    (OUT / "quality_report.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    (OUT / "spark_snapshot_manifest.json").write_text(json.dumps({
        "dataset_version": counts["dataset_version"],
        "source_raw_manifest_sha256": file_sha256(RAW / "manifest.json"),
        "files": {f"{name}.parquet": file_sha256(OUT / f"{name}.parquet")
                  for name in SPARK_SNAPSHOT_NAMES}}, indent=2), encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    build()
