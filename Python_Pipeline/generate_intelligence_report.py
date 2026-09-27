import pandas as pd
from config import PATHS, REPORTS_DIR

menu_df = pd.read_csv(f"{REPORTS_DIR}/menu_classification.csv")
customer_df = pd.read_csv(f"{REPORTS_DIR}/customer_segments.csv")
wastage_df = pd.read_csv(f"{REPORTS_DIR}/wastage_intelligence.csv")
churn_df = pd.read_csv(f"{REPORTS_DIR}/churn_risk.csv")
basket_df = pd.read_csv(f"{REPORTS_DIR}/basket_rules.csv")
promo_df = pd.read_csv(f"{REPORTS_DIR}/promotion_effectiveness.csv")
price_df = pd.read_csv(f"{REPORTS_DIR}/price_intelligence.csv")
location_df = pd.read_csv(f"{REPORTS_DIR}/location_intelligence.csv")
recommendations_df = pd.read_csv(f"{REPORTS_DIR}/recommendations.csv")
metrics_df = pd.read_csv(f"{REPORTS_DIR}/python_model_metrics.csv")

top_profitable = menu_df.sort_values("Total_Profit", ascending=False).head(5)
top_volume = menu_df.sort_values("Total_Quantity_Sold", ascending=False).head(5)
hidden_opportunities = menu_df[menu_df["Performance_Class"] == "Hidden Opportunity"]
low_performers = menu_df[menu_df["Performance_Class"] == "Low Performer"]
high_wastage = wastage_df[wastage_df["Risk_Level"] == "High"].head(5)
at_risk_customers = churn_df[churn_df["Churn_Risk"] == "High"]
segment_counts = customer_df["Customer_Segment"].value_counts()
top_combos = basket_df.sort_values("lift", ascending=False).head(5) if len(basket_df) > 0 else pd.DataFrame()
price_sensitive = price_df[price_df["Sensitivity"] == "Highly Price Sensitive"]
top_locations = location_df.sort_values("Total_Revenue", ascending=False).head(3)

report_lines = []
report_lines.append("# DineIQ Analytics - Restaurant Intelligence Report\n")

report_lines.append("## 1. Top 5 Most Profitable Dishes")
report_lines.append(top_profitable[["Item_Name", "Total_Profit", "Profit_Pct"]].to_markdown(index=False))

report_lines.append("\n## 2. Top 5 Highest-Volume Dishes")
report_lines.append(top_volume[["Item_Name", "Total_Quantity_Sold"]].to_markdown(index=False))

report_lines.append(f"\n## 3. Hidden Opportunities ({len(hidden_opportunities)} items)")
report_lines.append(hidden_opportunities[["Item_Name", "Profit_Pct", "Total_Quantity_Sold"]].head(5).to_markdown(index=False))

report_lines.append(f"\n## 4. Low Performers ({len(low_performers)} items)")
report_lines.append(low_performers[["Item_Name", "Profit_Pct", "Total_Quantity_Sold"]].head(5).to_markdown(index=False))

report_lines.append("\n## 5. Top 5 High-Wastage Items")
report_lines.append(high_wastage[["Item_Name", "Total_Wasted", "Total_Cost_Impact"]].to_markdown(index=False))

report_lines.append("\n## 6. Customer Segments Distribution")
report_lines.append(segment_counts.to_markdown())

report_lines.append(f"\n## 7. At-Risk (Churn) Customers: {len(at_risk_customers)} customers identified")

if len(top_combos) > 0:
    report_lines.append("\n## 8. Top Frequently Purchased Combinations")
    report_lines.append(top_combos[["antecedents", "consequents", "support", "confidence", "lift"]].to_markdown(index=False))

report_lines.append("\n## 9. Demand Forecast Model Performance")
report_lines.append(metrics_df.to_markdown(index=False))

report_lines.append(f"\n## 10. Price-Sensitive Items: {len(price_sensitive)} items identified")

report_lines.append("\n## 11. Top 3 Performing Locations")
report_lines.append(top_locations[["City", "Total_Revenue", "Total_Orders"]].to_markdown(index=False))

report_lines.append(f"\n## 12. Total Recommendations Generated: {len(recommendations_df)}")
report_lines.append(recommendations_df["Priority"].value_counts().to_markdown())

with open(f"{REPORTS_DIR}/restaurant_intelligence_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print("Restaurant Intelligence Report Generated!")