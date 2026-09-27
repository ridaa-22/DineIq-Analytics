import pandas as pd
from config import PATHS, REPORTS_DIR

df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])
df_menu = pd.read_csv(PATHS["menu_items"])
df_restaurants = pd.read_csv(PATHS["restaurants"])

df_order_items = df_order_items[df_order_items["Quantity"] > 0]
df_orders = df_orders.drop_duplicates(subset=["Order_ID"]).dropna(subset=["Order_DateTime"])
df_orders = df_orders[df_orders["Order_Status"] == "Completed"]
df_orders["Order_DateTime"] = pd.to_datetime(df_orders["Order_DateTime"])

df_orders["Hour"] = df_orders["Order_DateTime"].dt.hour
df_orders["DayName"] = df_orders["Order_DateTime"].dt.day_name()
df_orders["Month"] = df_orders["Order_DateTime"].dt.month
df_orders["IsWeekend"] = df_orders["Order_DateTime"].dt.dayofweek.isin([5, 6])

# --- Peak Hours ---
peak_hours = df_orders.groupby("Hour").size().reset_index(name="Order_Count").sort_values("Order_Count", ascending=False)

# --- Peak Days ---
peak_days = df_orders.groupby("DayName").size().reset_index(name="Order_Count").sort_values("Order_Count", ascending=False)

# --- Weekend vs Weekday ---
weekend_pattern = df_orders.groupby("IsWeekend").size().reset_index(name="Order_Count")
weekend_pattern["IsWeekend"] = weekend_pattern["IsWeekend"].map({True: "Weekend", False: "Weekday"})

# --- Monthly Trend ---
monthly_trend = df_orders.groupby("Month").size().reset_index(name="Order_Count").sort_values("Month")

# --- Location-wise Peak ---
location_peak = df_orders.merge(df_restaurants[["Location_ID", "City"]], on="Location_ID", how="left")
location_peak_hours = location_peak.groupby(["City", "Hour"]).size().reset_index(name="Order_Count")
location_top_hour = location_peak_hours.loc[location_peak_hours.groupby("City")["Order_Count"].idxmax()]

# --- Dine-in vs Delivery peaks ---
channel_peak = df_orders.groupby(["Channel", "Hour"]).size().reset_index(name="Order_Count")

# Save all outputs
peak_hours.to_csv(f"{REPORTS_DIR}/peak_hours.csv", index=False)
peak_days.to_csv(f"{REPORTS_DIR}/peak_days.csv", index=False)
weekend_pattern.to_csv(f"{REPORTS_DIR}/weekend_pattern.csv", index=False)
monthly_trend.to_csv(f"{REPORTS_DIR}/monthly_trend.csv", index=False)
location_top_hour.to_csv(f"{REPORTS_DIR}/location_peak_hours.csv", index=False)
channel_peak.to_csv(f"{REPORTS_DIR}/channel_peak_hours.csv", index=False)

print("Peak-Period Analysis Complete!")

# ============================================================
# LOCATION-SPECIFIC MENU CLASSIFICATION
# ============================================================

df_merged = df_order_items.merge(df_orders[["Order_ID", "Location_ID"]], on="Order_ID", how="inner")
df_merged["Line_Revenue"] = df_merged["Quantity"] * df_merged["Unit_Price"]

loc_item_stats = df_merged.groupby(["Location_ID", "Item_ID"]).agg(
    Total_Quantity_Sold=("Quantity", "sum"),
    Total_Revenue=("Line_Revenue", "sum")
).reset_index()

loc_item_stats = loc_item_stats.merge(df_menu[["Item_ID", "Item_Name", "Cost"]], on="Item_ID", how="left")
loc_item_stats["Total_Cost"] = loc_item_stats["Total_Quantity_Sold"] * loc_item_stats["Cost"]
loc_item_stats["Total_Profit"] = loc_item_stats["Total_Revenue"] - loc_item_stats["Total_Cost"]
loc_item_stats["Profit_Pct"] = round(loc_item_stats["Total_Profit"] / loc_item_stats["Total_Revenue"] * 100, 2)

volume_median = loc_item_stats["Total_Quantity_Sold"].median()
profit_median = loc_item_stats["Profit_Pct"].median()

def classify(row):
    high_volume = row["Total_Quantity_Sold"] >= volume_median
    high_profit = row["Profit_Pct"] >= profit_median
    if high_volume and high_profit:
        return "Profit Driver"
    elif high_volume and not high_profit:
        return "Volume Driver"
    elif not high_volume and high_profit:
        return "Hidden Opportunity"
    else:
        return "Low Performer"

loc_item_stats["Performance_Class"] = loc_item_stats.apply(classify, axis=1)
loc_item_stats = loc_item_stats.merge(df_restaurants[["Location_ID", "City"]], on="Location_ID", how="left")
loc_item_stats.to_csv(f"{REPORTS_DIR}/menu_classification_by_location.csv", index=False)

print("Location-Specific Menu Classification Complete!")