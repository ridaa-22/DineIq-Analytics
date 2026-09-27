import pandas as pd
import numpy as np
from config import PATHS, REPORTS_DIR

# 1. Data load karna
df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])
df_menu = pd.read_csv(PATHS["menu_items"])
df_ratings = pd.read_csv(PATHS["ratings"])
df_wastage = pd.read_csv(PATHS["wastage"])

# 2. Cleaning
df_order_items = df_order_items[df_order_items["Quantity"] > 0]
df_orders = df_orders.drop_duplicates(subset=["Order_ID"]).dropna(subset=["Order_DateTime"])
df_orders = df_orders[df_orders["Order_Status"] == "Completed"]
df_menu = df_menu[df_menu["Base_Price"] > 0]

# 3. Order_Items + Orders merge (sirf completed orders)
df_merged = df_order_items.merge(df_orders[["Order_ID", "Promotion_ID"]], on="Order_ID", how="inner")
df_merged["Line_Revenue"] = df_merged["Quantity"] * df_merged["Unit_Price"]

# 4. Per-item metrics calculate karna
item_stats = df_merged.groupby("Item_ID").agg(
    Total_Quantity_Sold=("Quantity", "sum"),
    Total_Revenue=("Line_Revenue", "sum"),
    Order_Count=("Order_ID", "nunique"),
    Promo_Order_Count=("Promotion_ID", lambda x: x.notna().sum())
).reset_index()

item_stats["Promotion_Dependency_Pct"] = round(
    item_stats["Promo_Order_Count"] / item_stats["Order_Count"] * 100, 2
)

# 5. Cost aur Profit Margin add karna
item_stats = item_stats.merge(df_menu[["Item_ID", "Item_Name", "Cost", "Base_Price"]], on="Item_ID", how="left")
item_stats["Total_Cost"] = item_stats["Total_Quantity_Sold"] * item_stats["Cost"]
item_stats["Total_Profit"] = item_stats["Total_Revenue"] - item_stats["Total_Cost"]
item_stats["Profit_Pct"] = round(item_stats["Total_Profit"] / item_stats["Total_Revenue"] * 100, 2)

# 6. Rating add karna
avg_rating = df_ratings[df_ratings["Stars"] <= 5].groupby("Item_ID")["Stars"].mean().rename("Avg_Rating")
item_stats = item_stats.merge(avg_rating, on="Item_ID", how="left")

# 7. Wastage add karna
wastage_stats = df_wastage[df_wastage["Quantity_Wasted"] > 0].groupby("Item_ID")["Quantity_Wasted"].sum().rename("Total_Wasted")
item_stats = item_stats.merge(wastage_stats, on="Item_ID", how="left")
item_stats["Total_Wasted"] = item_stats["Total_Wasted"].fillna(0)
item_stats["Wastage_Pct"] = round(
    item_stats["Total_Wasted"] / (item_stats["Total_Quantity_Sold"] + item_stats["Total_Wasted"]) * 100, 2
)

# 8. Multi-factor classification (median-based thresholds)
volume_median = item_stats["Total_Quantity_Sold"].median()
profit_median = item_stats["Profit_Pct"].median()

def classify_item(row):
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

item_stats["Performance_Class"] = item_stats.apply(classify_item, axis=1)

# 9. Tricky cases dhoondna
tricky_cases = []
for _, row in item_stats.iterrows():
    if row["Total_Quantity_Sold"] >= volume_median and row["Total_Profit"] < 0:
        tricky_cases.append({"Item_ID": row["Item_ID"], "Item_Name": row["Item_Name"], "Case": "High-selling but loss-making"})
    if row["Profit_Pct"] >= profit_median and row["Total_Quantity_Sold"] < volume_median * 0.3:
        tricky_cases.append({"Item_ID": row["Item_ID"], "Item_Name": row["Item_Name"], "Case": "High-margin but rarely purchased"})
    if row["Wastage_Pct"] > 20 and row["Total_Quantity_Sold"] >= volume_median:
        tricky_cases.append({"Item_ID": row["Item_ID"], "Item_Name": row["Item_Name"], "Case": "Popular but excessive wastage"})
    if row.get("Avg_Rating", 0) >= 4.5 and row["Profit_Pct"] < profit_median:
        tricky_cases.append({"Item_ID": row["Item_ID"], "Item_Name": row["Item_Name"], "Case": "Highly rated but poor profitability"})
    if row["Promotion_Dependency_Pct"] > 50:
        tricky_cases.append({"Item_ID": row["Item_ID"], "Item_Name": row["Item_Name"], "Case": "Promotion-dependent dish"})

df_tricky = pd.DataFrame(tricky_cases)

# 10. Save outputs
item_stats.to_csv(f"{REPORTS_DIR}/menu_classification.csv", index=False)
df_tricky.to_csv(f"{REPORTS_DIR}/menu_tricky_cases.csv", index=False)

print("Menu Intelligence Complete!")
print("\nClassification Summary:")
print(item_stats["Performance_Class"].value_counts())
print("\nTricky Cases Found:", len(df_tricky))