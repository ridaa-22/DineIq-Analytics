import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from config import PATHS, REPORTS_DIR, MODELS_DIR

# 1. Data load karna
df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])

# 2. Cleaning (negative qty, duplicates, invalid dates)
df_order_items = df_order_items[df_order_items["Quantity"] > 0]
df_orders = df_orders.drop_duplicates(subset=["Order_ID"])
df_orders = df_orders.dropna(subset=["Order_DateTime"])
df_orders["Order_DateTime"] = pd.to_datetime(df_orders["Order_DateTime"])
df_orders = df_orders[df_orders["Order_Status"] == "Completed"]

# 3. RFM Calculation
df_merged = df_order_items.merge(df_orders, on="Order_ID", how="inner")
df_merged["Line_Total"] = df_merged["Quantity"] * df_merged["Unit_Price"]

snapshot_date = df_orders["Order_DateTime"].max() + pd.Timedelta(days=1)

rfm = df_orders.groupby("Customer_ID").agg({
    "Order_DateTime": lambda x: (snapshot_date - x.max()).days,
    "Order_ID": "count"
})
rfm.columns = ["Recency", "Frequency"]

monetary = df_merged.groupby("Customer_ID")["Line_Total"].sum().rename("Monetary")
rfm = rfm.join(monetary).dropna()

# 4. Scaling + KMeans
scaler = StandardScaler()
rfm_scaled = scaler.fit_transform(rfm)

kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
rfm["Cluster"] = kmeans.fit_predict(rfm_scaled)

# 5. Cluster profiling (labels ke liye)
cluster_profile = rfm.groupby("Cluster").agg({
    "Recency": "mean",
    "Frequency": "mean",
    "Monetary": "mean"
}).round(2)
cluster_profile["Customer_Count"] = rfm.groupby("Cluster").size()

print("Cluster Profile:")
print(cluster_profile)

# 6. Business labels assign karna (profile ke hisaab se)
def label_cluster(row):
    if row["Monetary"] > cluster_profile["Monetary"].median() and row["Frequency"] > cluster_profile["Frequency"].median():
        return "High-Value Loyal"
    elif row["Recency"] > cluster_profile["Recency"].median():
        return "At-Risk"
    elif row["Frequency"] > cluster_profile["Frequency"].median():
        return "Frequent"
    else:
        return "Occasional"

cluster_profile["Segment_Label"] = cluster_profile.apply(label_cluster, axis=1)
label_map = cluster_profile["Segment_Label"].to_dict()
rfm["Customer_Segment"] = rfm["Cluster"].map(label_map)

# 7. Save artifacts
joblib.dump(kmeans, f"{MODELS_DIR}/customer_kmeans.joblib")
joblib.dump(scaler, f"{MODELS_DIR}/customer_scaler.joblib")

rfm.reset_index().to_csv(f"{REPORTS_DIR}/customer_segments.csv", index=False)
cluster_profile.reset_index().to_csv(f"{REPORTS_DIR}/customer_cluster_profile.csv", index=False)

print("\nCustomer Segmentation Complete!")
print("Saved: customer_segments.csv, customer_cluster_profile.csv, kmeans model, scaler")