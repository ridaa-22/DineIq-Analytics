"""Refresh the current slow-moving evidence from the same scoped API rules."""

import csv
import json
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from fast_apis import database
from fast_apis.routes.dynamic import slow_moving


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "Reports"
BEGIN = "<!-- SLOW_MOVING_BEGIN -->"
END = "<!-- SLOW_MOVING_END -->"


def main():
    with tempfile.TemporaryDirectory() as folder, patch.object(database, "DB_PATH", Path(folder) / "app.sqlite3"):
        rows = slow_moving(limit=200, offset=0, user={"roles": ["ADMIN"], "id": None})["items"]
    REPORTS.mkdir(parents=True, exist_ok=True)
    columns = ["Item_ID", "Item_Name", "Category_ID", "Location_ID", "Scope", "Slow_Moving_Status",
               "Severity", "Evidence", "Reason", "History_Status", "Recommended_Action",
               "Slow_Moving_Rule_Version"]
    with (REPORTS / "CURRENT_SLOW_MOVING.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "Evidence": json.dumps(row["Evidence"], sort_keys=True)})
    counts = Counter(row["Slow_Moving_Status"] for row in rows)
    report = REPORTS / "CURRENT_RESTAURANT_INTELLIGENCE.md"
    content = report.read_text(encoding="utf-8")
    summary = (f"| Slow-moving | {counts['SLOW_MOVER']} confirmed slow movers, "
               f"{counts['WATCHLIST']} watchlist, {counts['HIDDEN_OPPORTUNITY']} hidden opportunities, "
               f"{counts['SEASONAL_REVIEW']} seasonal review, {counts['INSUFFICIENT_HISTORY']} insufficient history "
               "| `Reports/CURRENT_SLOW_MOVING.csv`; scoped multifactor rules; one-year seasonality is provisional |")
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Slow-moving |"):
            lines[index] = summary
            break
    else:
        menu_index = next(index for index, line in enumerate(lines) if line.startswith("| Menu |"))
        lines.insert(menu_index + 1, summary)
    content = "\n".join(lines)
    watch = [row for row in rows if row["Slow_Moving_Status"] == "WATCHLIST"][:5]
    detail = [BEGIN, "## Slow-moving assessment", "",
              f"These are descriptive review flags, not verified demand labels. This clean snapshot has "
              f"{counts['SLOW_MOVER']} confirmed global slow movers under the documented rule.", "",
              "| Item | Status | Sales | 30-day trend | Repeat rate | Action |",
              "| --- | --- | ---: | ---: | ---: | --- |"]
    for row in watch:
        evidence = row["Evidence"]
        detail.append(f"| {row['Item_ID']} | {row['Slow_Moving_Status']} | {evidence['sales']} | "
                      f"{evidence['recent_trend_percent']:.2f}% | {evidence['repeat_purchase_rate']:.3f} | "
                      f"{row['Recommended_Action']} |")
    detail.append(END)
    section = "\n".join(detail)
    if BEGIN in content and END in content:
        content = content[:content.index(BEGIN)] + section + content[content.index(END) + len(END):]
    else:
        content += "\n\n" + section
    report.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"items": len(rows), "status_counts": dict(counts)}))


if __name__ == "__main__":
    main()
