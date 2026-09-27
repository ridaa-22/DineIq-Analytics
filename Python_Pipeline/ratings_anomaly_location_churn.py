import pandas as pd
import numpy as np
from config import PATHS, REPORTS_DIR

df_ratings = pd.read_csv(PATHS["ratings"])
df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])
df_restaurants = pd.read_csv(PATHS["restaurants"])
df_menu = pd.read_csv(PATHS["menu_items"])

df_orders_clean = df_orders.drop_duplicates(subset=["Order_ID"]).dropna(subset=["Order_DateTime"])
df_orders_clean = df_orders_clean[df_orders_clean["Order_Status"] == "Completed"]
df_order_items_clean = df_order_items[df_order_items["Quantity"] > 0]

# --- Rating Analysis + Anomalies ---
df_ratings_valid = df_ratings[df_ratings["Stars"].between(1, 5)]
rating_by_item = df_ratings_valid.groupby("Item_ID")["Stars"].agg(["mean", "count"]).reset_index()
rating_by_item.columns = ["Item_ID", "Avg_Rating", "Rating_Count"]

anomaly_ratings = df_ratings[~df_ratings["Stars"].between(1, 5)]
anomaly_summary = anomaly_ratings.groupby("Item_ID").size().reset_index(name="Invalid_Rating_Count")
anomaly_summary.to_csv(f"{REPORTS_DIR}/anomalies.csv", index=False)

rating_by_item = rating_by_item.merge(df_menu[["Item_ID", "Item_Name"]], on="Item_ID", how="left")
rating_by_item.to_csv(f"{REPORTS_DIR}/rating_analysis.csv", index=False)

# --- Sales Anomaly Detection ---
df_merged = df_order_items_clean.merge(df_orders_clean[["Order_ID"]], on="Order_ID", how="inner")
df_merged["Line_Total"] = df_merged["Quantity"] * df_merged["Unit_Price"]
q1, q3 = df_merged["Line_Total"].quantile([0.25, 0.75])
iqr = q3 - q1
upper_bound = q3 + 1.5 * iqr
sales_anomalies = df_merged[df_merged["Line_Total"] > upper_bound]
sales_anomalies.to_csv(f"{REPORTS_DIR}/sales_anomalies.csv", index=False)

# --- Location Intelligence ---
df_loc_merged = df_merged.merge(df_orders_clean[["Order_ID", "Location_ID"]], on="Order_ID", how="left")
df_loc_merged = df_loc_merged.merge(df_restaurants[["Location_ID", "City"]], on="Location_ID", how="left")

location_stats = df_loc_merged.groupby(["Location_ID", "City"]).agg(
    Total_Revenue=("Line_Total", "sum"),
    Total_Orders=("Order_ID", "nunique"),
    Avg_Order_Value=("Line_Total", "mean")
).reset_index()
location_stats.to_csv(f"{REPORTS_DIR}/location_intelligence.csv", index=False)

# --- Channel Analysis ---
df_channel_merged = df_merged.merge(df_orders_clean[["Order_ID", "Channel"]], on="Order_ID", how="left")
channel_stats = df_channel_merged.groupby("Channel").agg(
    Total_Revenue=("Line_Total", "sum"),
    Total_Orders=("Order_ID", "nunique"),
    Avg_Order_Value=("Line_Total", "mean")
).reset_index()
channel_stats.to_csv(f"{REPORTS_DIR}/channel_intelligence.csv", index=False)

# --- Churn Risk ---
df_orders_clean["Order_DateTime"] = pd.to_datetime(df_orders_clean["Order_DateTime"])
snapshot_date = df_orders_clean["Order_DateTime"].max() + pd.Timedelta(days=1)

customer_recency = df_orders_clean.groupby("Customer_ID")["Order_DateTime"].agg(
    lambda x: (snapshot_date - x.max()).days
).rename("Recency_Days").reset_index()

customer_freq = df_orders_clean.groupby("Customer_ID").size().rename("Frequency").reset_index()
churn_df = customer_recency.merge(customer_freq, on="Customer_ID")

recency_threshold = churn_df["Recency_Days"].quantile(0.75)
churn_df["Churn_Risk"] = churn_df["Recency_Days"].apply(
    lambda x: "High" if x >= recency_threshold else "Low"
)
churn_df.to_csv(f"{REPORTS_DIR}/churn_risk.csv", index=False)

print("Ratings, Anomalies, Location, Channel, Churn Analysis Complete!")