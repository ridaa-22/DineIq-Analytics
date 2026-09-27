import pandas as pd
from config import PATHS, REPORTS_DIR

df_wastage = pd.read_csv(PATHS["wastage"])
df_menu = pd.read_csv(PATHS["menu_items"])
df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])
df_pricing = pd.read_csv(PATHS["pricing_history"])
df_promotions = pd.read_csv(PATHS["promotions"])
df_restaurants = pd.read_csv(PATHS["restaurants"])

# --- Wastage Intelligence ---
df_wastage = df_wastage[df_wastage["Quantity_Wasted"] > 0]
wastage_by_item = df_wastage.groupby("Item_ID").agg(
    Total_Wasted=("Quantity_Wasted", "sum"),
    Total_Cost_Impact=("Cost_Impact", "sum")
).reset_index().merge(df_menu[["Item_ID", "Item_Name"]], on="Item_ID", how="left")

wastage_by_location = df_wastage.groupby("Location_ID").agg(
    Total_Wasted=("Quantity_Wasted", "sum"),
    Total_Cost_Impact=("Cost_Impact", "sum")
).reset_index().merge(df_restaurants[["Location_ID", "City"]], on="Location_ID", how="left")

wastage_threshold = wastage_by_item["Total_Wasted"].quantile(0.75)
wastage_by_item["Risk_Level"] = wastage_by_item["Total_Wasted"].apply(
    lambda x: "High" if x >= wastage_threshold else "Low"
)
wastage_by_item.to_csv(f"{REPORTS_DIR}/wastage_intelligence.csv", index=False)

# --- Price Sensitivity ---
df_pricing = df_pricing.sort_values(["Item_ID", "Effective_Date"])
df_pricing["Price_Change_Pct"] = df_pricing.groupby("Item_ID")["Price"].pct_change() * 100

df_order_items_clean = df_order_items[df_order_items["Quantity"] > 0]
demand_by_item = df_order_items_clean.groupby("Item_ID")["Quantity"].sum().rename("Total_Demand")

price_sensitivity = df_pricing.groupby("Item_ID")["Price_Change_Pct"].mean().dropna().reset_index()
price_sensitivity = price_sensitivity.merge(demand_by_item, on="Item_ID", how="left")
price_sensitivity = price_sensitivity.merge(df_menu[["Item_ID", "Item_Name"]], on="Item_ID", how="left")

def sensitivity_label(pct_change):
    if abs(pct_change) > 10:
        return "Highly Price Sensitive"
    elif abs(pct_change) > 3:
        return "Moderately Price Sensitive"
    else:
        return "Low Price Sensitivity"

price_sensitivity["Sensitivity"] = price_sensitivity["Price_Change_Pct"].apply(sensitivity_label)
price_sensitivity.to_csv(f"{REPORTS_DIR}/price_intelligence.csv", index=False)

# --- Promotion Effectiveness ---
df_orders_completed = df_orders[df_orders["Order_Status"] == "Completed"].drop_duplicates(subset=["Order_ID"])
df_merged_promo = df_order_items_clean.merge(df_orders_completed[["Order_ID", "Promotion_ID"]], on="Order_ID", how="inner")
df_merged_promo["Line_Revenue"] = df_merged_promo["Quantity"] * df_merged_promo["Unit_Price"]

promo_orders = df_merged_promo[df_merged_promo["Promotion_ID"].notna()]
non_promo_orders = df_merged_promo[df_merged_promo["Promotion_ID"].isna()]

promo_summary = df_promotions.copy()
promo_stats = promo_orders.groupby("Promotion_ID").agg(
    Order_Volume=("Order_ID", "nunique"),
    Total_Revenue=("Line_Revenue", "sum"),
    Avg_Order_Value=("Line_Revenue", "mean")
).reset_index()
promo_summary = promo_summary.merge(promo_stats, on="Promotion_ID", how="left")

avg_non_promo_margin = non_promo_orders["Line_Revenue"].mean()
promo_summary["Trap_Flag"] = promo_summary["Avg_Order_Value"].apply(
    lambda x: "Possible Trap (Lower AOV than non-promo)" if pd.notna(x) and x < avg_non_promo_margin else "OK"
)
promo_summary.to_csv(f"{REPORTS_DIR}/promotion_effectiveness.csv", index=False)

print("Wastage, Pricing, Promotion Intelligence Complete!")