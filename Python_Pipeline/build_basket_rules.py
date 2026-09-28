"""Mine observed item pairs from cleaned completed orders with transparent thresholds."""

from collections import Counter
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "phase1-v1"


def build():
    sales = pd.read_parquet(DATA / "sales.parquet", columns=["Order_ID", "Item_ID"])
    basket = sales.drop_duplicates().groupby("Order_ID").Item_ID.agg(lambda values: sorted(set(values)))
    single, pair = Counter(), Counter()
    for items in basket:
        single.update(items)
        pair.update(combinations(items, 2))
    total = len(basket)
    rules = []
    for (left, right), count in pair.items():
        if count < 100:
            continue
        support = count / total
        for antecedent, consequent in ((left, right), (right, left)):
            confidence = count / single[antecedent]
            lift = confidence / (single[consequent] / total)
            if lift >= 1.05:
                rules.append({"Antecedent_Item_ID": antecedent, "Consequent_Item_ID": consequent,
                              "Pair_Count": count, "Support": support, "Confidence": confidence, "Lift": lift})
    result = pd.DataFrame(rules, columns=["Antecedent_Item_ID", "Consequent_Item_ID", "Pair_Count",
                                          "Support", "Confidence", "Lift"])
    if not result.empty:
        result = result.sort_values(["Lift", "Pair_Count"], ascending=False)
    result.to_csv(DATA / "basket_rules.csv", index=False)
    print(f"baskets={total}, evidence-backed rules={len(result)}")


if __name__ == "__main__":
    build()
