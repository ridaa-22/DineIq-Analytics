import pandas as pd
from config import PATHS, REPORTS_DIR

menu_df = pd.read_csv(f"{REPORTS_DIR}/menu_classification.csv")
wastage_df = pd.read_csv(f"{REPORTS_DIR}/wastage_intelligence.csv")
churn_df = pd.read_csv(f"{REPORTS_DIR}/churn_risk.csv")
promo_df = pd.read_csv(f"{REPORTS_DIR}/promotion_effectiveness.csv")

recommendations = []
rec_id = 1

for _, row in menu_df.iterrows():
    if row["Performance_Class"] == "Hidden Opportunity":
        recommendations.append({
            "Recommendation_ID": rec_id, "Entity": row["Item_Name"], "Type": "Menu Optimization",
            "Action": "Promote item (high margin, low visibility)",
            "Priority": "High",
            "Evidence": f"Profit_Pct={row['Profit_Pct']}, Quantity_Sold={row['Total_Quantity_Sold']}",
            "Reason": "Good profitability but low sales volume"
        })
        rec_id += 1
    elif row["Performance_Class"] == "Low Performer":
        recommendations.append({
            "Recommendation_ID": rec_id, "Entity": row["Item_Name"], "Type": "Menu Optimization",
            "Action": "Review for redesign or removal",
            "Priority": "Medium",
            "Evidence": f"Profit_Pct={row['Profit_Pct']}, Quantity_Sold={row['Total_Quantity_Sold']}",
            "Reason": "Weak demand and weak profitability"
        })
        rec_id += 1

for _, row in wastage_df[wastage_df["Risk_Level"] == "High"].iterrows():
    recommendations.append({
        "Recommendation_ID": rec_id, "Entity": row["Item_Name"], "Type": "Inventory",
        "Action": "Reduce preparation quantity",
        "Priority": "Critical",
        "Evidence": f"Total_Wasted={row['Total_Wasted']}, Cost_Impact={row['Total_Cost_Impact']}",
        "Reason": "High wastage cost impact"
    })
    rec_id += 1

for _, row in churn_df[churn_df["Churn_Risk"] == "High"].head(50).iterrows():
    recommendations.append({
        "Recommendation_ID": rec_id, "Entity": f"Customer_{row['Customer_ID']}", "Type": "Customer Targeting",
        "Action": "Send re-engagement offer",
        "Priority": "Medium",
        "Evidence": f"Recency_Days={row['Recency_Days']}",
        "Reason": "Increasing inactivity, at risk of churn"
    })
    rec_id += 1

df_recommendations = pd.DataFrame(recommendations)
df_recommendations.to_csv(f"{REPORTS_DIR}/recommendations.csv", index=False)

print("Recommendation Engine Complete! Total recommendations:", len(df_recommendations))


def what_if_price_change(item_id, price_change_pct, menu_df):
    item = menu_df[menu_df["Item_ID"] == item_id].iloc[0]
    baseline_revenue = item["Total_Revenue"]
    estimated_demand_change_pct = -price_change_pct * 0.8
    new_quantity = item["Total_Quantity_Sold"] * (1 + estimated_demand_change_pct / 100)
    new_price = item["Base_Price"] * (1 + price_change_pct / 100)
    scenario_revenue = new_quantity * new_price

    return {
        "is_estimate": True,
        "Item_ID": item_id,
        "baseline_revenue": round(baseline_revenue, 2),
        "scenario_revenue": round(scenario_revenue, 2),
        "delta": round(scenario_revenue - baseline_revenue, 2),
        "assumptions": "Linear demand elasticity assumption (0.8 factor), not a causal guarantee"
    }


sample_item_id = menu_df.iloc[0]["Item_ID"]
example = what_if_price_change(sample_item_id, 10, menu_df)
pd.DataFrame([example]).to_json(f"{REPORTS_DIR}/what_if_examples.json", orient="records", indent=2)

print("What-If Example:", example)