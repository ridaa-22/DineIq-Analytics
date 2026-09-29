"""Refresh versioned promotion evidence through the supported analytical API logic."""

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fast_apis import database
from fast_apis.routes.dynamic import promotions, recommendations


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "Reports"


def main():
    # Seed a disposable application database from the immutable Phase 1 raw catalog.
    # Managed live changes therefore cannot silently alter versioned report evidence.
    with tempfile.TemporaryDirectory() as folder, patch.object(database, "DB_PATH", Path(folder) / "app.sqlite3"):
        user = {"roles": ["ADMIN"], "id": None}
        campaigns = promotions(user=user)["campaigns"]
        actions = [row for row in recommendations(user=user)["recommendations"] if row["type"] == "promotion"]
    REPORTS.mkdir(parents=True, exist_ok=True)
    columns = ["Promotion_ID", "promotion_name", "start_date", "end_date", "eligible_item_count",
               "quantity", "revenue", "contribution", "orders", "customers", "aov",
               "tagged_campaign_orders", "repeat_customers", "wastage_cost", "promotion_trap",
               "comparison_available", "before_quantity", "before_contribution",
               "after_quantity", "after_contribution"]
    with (REPORTS / "CURRENT_PROMOTION_EFFECTIVENESS.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        for row in campaigns:
            flattened = {key: row[key] for key in columns if key in row}
            for period in ("before", "after"):
                flattened[f"{period}_quantity"] = row[period]["quantity"] if row[period] else None
                flattened[f"{period}_contribution"] = row[period]["contribution"] if row[period] else None
            writer.writerow(flattened)
    stable_actions = [{key: value for key, value in row.items() if key != "generated_at"} for row in actions]
    (REPORTS / "CURRENT_PROMOTION_RECOMMENDATIONS.json").write_text(
        json.dumps(stable_actions, indent=2), encoding="utf-8")
    campaign_one = next(row for row in campaigns if row["Promotion_ID"] == 1)
    report = REPORTS / "CURRENT_RESTAURANT_INTELLIGENCE.md"
    content = report.read_text(encoding="utf-8")
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Promotions |"):
            lines[index] = ("| Promotions | Campaign 1 targets item 4 only; "
                            f"{campaign_one['eligible_item_count']} eligible item, "
                            f"{campaign_one['quantity']:,.0f} during-window portions, "
                            f"PKR {campaign_one['contribution']:,.2f} contribution; "
                            f"trap flag {campaign_one['promotion_trap']} | "
                            "`Reports/CURRENT_PROMOTION_EFFECTIVENESS.csv`; Asia/Karachi local-day windows; observational |")
            break
    else:
        raise RuntimeError("Promotion section missing from current report")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"campaigns": len(campaigns), "promotion_recommendations": len(stable_actions),
                      "campaign_1_eligible_items": campaign_one["eligible_item_count"],
                      "campaign_1_trap": campaign_one["promotion_trap"]}))


if __name__ == "__main__":
    main()
