# Campaign eligibility and restaurant calendar

Historical campaign population uses `get_eligible_sales_for_promotion` in `Python_Pipeline/campaign_eligibility.py`. It is the shared selector for promotion analytics, trap detection, promotion recommendations, campaign-scoped what-if estimates, and refreshed report evidence.

| Campaign fields | Eligible sales |
| --- | --- |
| `applicable_item_id` set | Only that item. A category value on the same campaign is descriptive and never widens this set. |
| Item null, `applicable_category_id` set | All items in that category. |
| Both item and category null | All items. |
| `location_id` set | Intersect the selected item/category/global population with that location. Null location means all locations in the caller's authorized scope. |

The campaign start and end are inclusive **Asia/Karachi calendar dates**. The implementation selects timestamps in `[start at 00:00, day after end at 00:00)`. The same local midnight utility supplies price-change windows and API business-date filtering. Source offset timestamps are converted to Asia/Karachi when cleaned; naive business dates are interpreted as local dates. Campaign assignment on an order does not make unrelated basket lines eligible.

`Reports/CURRENT_PROMOTION_EFFECTIVENESS.csv` and `Reports/CURRENT_PROMOTION_RECOMMENDATIONS.json` are regenerated with `python -m scripts.refresh_promotion_evidence`. The script uses the current analytical API logic and a temporary catalog seeded from immutable Phase 1 raw data. It updates the promotion row in `Reports/CURRENT_RESTAURANT_INTELLIGENCE.md`. The older `Reports/promotion_effectiveness.csv` is a legacy artifact from another dataset and is not the source for current findings. Historical window comparisons remain observational; campaign targeting does not establish causal lift.
