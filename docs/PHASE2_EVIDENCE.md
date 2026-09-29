# Phase 2 verification

The prior `item OR category` selector returned 15 distinct items for campaign 1, whose raw target is item 4 and category 4. The corrected shared selector returns only item 4. The campaign API reports `eligible_item_count=1` for campaign 1.

`python -m scripts.refresh_promotion_evidence` generated 20 rows in `Reports/CURRENT_PROMOTION_EFFECTIVENESS.csv` and one promotion action in `Reports/CURRENT_PROMOTION_RECOMMENDATIONS.json`. Campaign 1 has 2,979 eligible during-window portions, PKR -248,850 contribution, and a true sales-up/contribution-down trap. Those values are observational findings from the versioned clean dataset.

`python -m pytest tests/test_campaign_calendar.py tests/test_dynamic_app.py tests/test_business_methods.py -q` passed 23 tests. After the final location and local-date adjustments, the focused seven-test command covering campaign population, midnight boundaries, valid/invalid management writes, campaign what-if, live modules, and promotion traps passed. The timestamp boundary test verifies 23:59 and 00:00 Asia/Karachi at both campaign edges and local date filtering.

Limits: Historical Parquet was not rebuilt because source offset timestamps were already converted to Asia/Karachi; this phase corrects downstream window interpretation. The older legacy promotion CSV remains from another dataset and is identified in `PROMOTION_TIME_CONTRACT.md`. Campaign comparisons do not establish causal effects. Live managed campaigns can differ from versioned report evidence, which deliberately uses a disposable raw-seeded catalog.
