import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from config import PATHS, REPORTS_DIR, MODELS_DIR

df_wastage = pd.read_csv(PATHS["wastage"])
df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])
df_menu = pd.read_csv(PATHS["menu_items"])

df_wastage = df_wastage[df_wastage["Quantity_Wasted"] > 0]
df_order_items = df_order_items[df_order_items["Quantity"] > 0]
df_orders = df_orders.drop_duplicates(subset=["Order_ID"]).dropna(subset=["Order_DateTime"])
df_orders["Order_DateTime"] = pd.to_datetime(df_orders["Order_DateTime"])
df_orders["DayOfWeek"] = df_orders["Order_DateTime"].dt.dayofweek

# Historical demand per item
demand_by_item = df_order_items.groupby("Item_ID")["Quantity"].sum().rename("Historical_Demand")

# Historical wastage per item
wastage_by_item = df_wastage.groupby("Item_ID").agg(
    Total_Wasted=("Quantity_Wasted", "sum"),
    Wastage_Events=("Wastage_ID", "count")
).reset_index()

wastage_by_item = wastage_by_item.merge(demand_by_item, on="Item_ID", how="left")
wastage_by_item = wastage_by_item.merge(df_menu[["Item_ID", "Item_Name"]], on="Item_ID", how="left")
wastage_by_item["Historical_Demand"] = wastage_by_item["Historical_Demand"].fillna(0)
wastage_by_item["Wastage_Ratio"] = wastage_by_item["Total_Wasted"] / (wastage_by_item["Historical_Demand"] + wastage_by_item["Total_Wasted"])

# Label: High risk if wastage ratio in top 25%
risk_threshold = wastage_by_item["Wastage_Ratio"].quantile(0.75)
wastage_by_item["Risk_Label"] = (wastage_by_item["Wastage_Ratio"] >= risk_threshold).astype(int)

# Features + model
features = ["Historical_Demand", "Total_Wasted", "Wastage_Events"]
X = wastage_by_item[features]
y = wastage_by_item["Risk_Label"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
preds = model.predict(X_test)

accuracy = accuracy_score(y_test, preds)
print("Wastage Risk Model Accuracy:", round(accuracy, 3))
print(classification_report(y_test, preds))

wastage_by_item["Predicted_Risk"] = model.predict(X)
wastage_by_item["Risk_Level"] = wastage_by_item["Predicted_Risk"].map({1: "High", 0: "Low"})

wastage_by_item.to_csv(f"{REPORTS_DIR}/wastage_risk_prediction.csv", index=False)
joblib.dump(model, f"{MODELS_DIR}/wastage_risk_model.joblib")

print("Wastage Risk Prediction Complete!")