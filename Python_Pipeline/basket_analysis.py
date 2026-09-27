import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
from config import PATHS, REPORTS_DIR

df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])
df_menu = pd.read_csv(PATHS["menu_items"])

df_order_items = df_order_items[df_order_items["Quantity"] > 0]
df_orders = df_orders.drop_duplicates(subset=["Order_ID"])
df_orders = df_orders[df_orders["Order_Status"] == "Completed"]

df_merged = df_order_items.merge(df_orders[["Order_ID"]], on="Order_ID", how="inner")
df_merged = df_merged.merge(df_menu[["Item_ID", "Item_Name"]], on="Item_ID", how="left")

baskets = df_merged.groupby("Order_ID")["Item_Name"].apply(list)
baskets = baskets[baskets.apply(len) > 1].tolist()

sample_baskets = baskets[:20000]

te = TransactionEncoder()
te_array = te.fit(sample_baskets).transform(sample_baskets)
df_encoded = pd.DataFrame(te_array, columns=te.columns_)

frequent_items = apriori(df_encoded, min_support=0.01, use_colnames=True)
rules = association_rules(frequent_items, metric="lift", min_threshold=1.0)
rules = rules.sort_values("lift", ascending=False)

rules_export = rules[["antecedents", "consequents", "support", "confidence", "lift"]].copy()
rules_export["antecedents"] = rules_export["antecedents"].apply(lambda x: ", ".join(list(x)))
rules_export["consequents"] = rules_export["consequents"].apply(lambda x: ", ".join(list(x)))
rules_export.to_csv(f"{REPORTS_DIR}/basket_rules.csv", index=False)

bundles = rules_export[rules_export["lift"] > 1.2].head(20)
bundles.to_csv(f"{REPORTS_DIR}/bundle_recommendations.csv", index=False)

print("Basket Analysis Complete! Rules found:", len(rules_export))