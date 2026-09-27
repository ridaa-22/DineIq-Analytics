# Phase 1 synthetic business scenarios

These are designed data-generating effects, not predictions, discovered insights, or fixed Performance_Class labels. Item/customer IDs refer to `phase1-v1`, not retroactive assertions about the untouched legacy data. See [DATA_CONTRACT.md](DATA_CONTRACT.md) for units, dates, campaign scope, and explicit dirty fixtures.

| Scenario | Generator construction | Acceptance evidence |
|---|---|---|
| High-selling loss-making item | Item 1 has high basket weight, PKR 1,000 price versus PKR 1,050 preparation cost; campaign 2 deepens losses | Completed quantity >5× median item quantity and total contribution <0 |
| Profitable rarely purchased item | Item 2 has PKR 1,200 price, PKR 200 cost, very low selection weight | Quantity <0.1× median and positive contribution |
| Popular high-wastage item | Item 3 is popular; all observed item-3 demand days receive ~70% overproduction relative to sold portions | Observed waste/sold ratio >0.5, with valid preparation/cost balances |
| Misleading promotion | Item 4 campaign 1 runs June 1–30, 40% discount, high conditional demand weight; PKR 900 price/650 cost | June units >3× May units but June contribution <0; profit is not inferred from sales alone |
| Location variation | Item 5 gets large weight at location 1 and near-zero at location 2 | Location-1 quantity >20× location-2 quantity |
| Price-sensitive item | Item 6 price rises PKR 1,000→1,400 on Jul 1; basket weight drops 10→1 | First-half quantity >3× second-half; transaction prices match history |
| Weekend-only behavior | Item 7 weight 14 on weekends versus 0.02 on weekdays | Weekend quantity >10× weekday quantity |
| Seasonal dish | Item 8 concentrated in January/December | Those two months exceed the other ten combined by >10× |
| New item / insufficient history | Item 9 introduced Dec 1 | No lines before introduction; no invented earlier history |
| High rating / weak profitability | Item 10 receives 5-star feedback but only PKR 10 unit contribution before operational waste | Average stars >4.5, unit contribution <PKR 20 |
| Low rating / high sales | Item 11 has high basket weight, feedback of 1–2 stars | Average stars <2.1 and quantity >3× median |
| Promotion dependency | Item 12 primarily selected with campaign 3 | Eligible promoted quantity >3× nonpromoted quantity |
| Sales anomaly and rating burst | Item 13 weight spikes on Aug 15; purchased-item feedback for those orders is synchronized to Aug 18 noon, 5 stars | At least ten feedback events at one timestamp; underlying orders/items/customers remain valid |
| High-value customers | Customer IDs 1–1000 are disproportionately chosen in later orders | Higher observed order activity; cohort membership is fixture provenance, not a model feature |
| Churned / at-risk customers | IDs 1001–2000 transact only through Jun 30 | No later order; relative to Jan 2026 they have long inactivity |
| New customers | IDs 49001–50000 sign up Dec 1 and transact thereafter | No order predates signup; first-order assignment ensures these customers are represented |
| Peaks and general seasonality | Weekend/winter days and lunch/dinner hours have larger sampling weights | Persisted generation has time variation; formal Spark peak analysis is a later phase |
| Cancelled transactions | Approximately 4% of order headers are cancelled | Raw audit population retains them; completed-demand/preparation fixtures exclude them |

Campaign 1 is the harmful-promotion fixture; campaign 2 discounts item 1; campaign 3 targets item 12. Campaigns 4–20 target designated items in dated windows. Item-targeted campaign fields are intentional contract additions; campaign category always matches the item.

Basket generation preserves all legacy line IDs and order references, but repairs item assignments and time-effective prices. The legacy large-basket scaffold remains (roughly ten lines per order). Repeated items within one basket are legitimate distinct lines, not duplicate line IDs. Basket-analysis results must acknowledge this synthetic limitation; a new realism requirement for basket-size diversity would require an explicit later version rather than silently changing this snapshot.

Promotion and price effects are deliberately associated with demand in the generator. They are not randomized causal experiments: season, basket composition, and other effects can confound an observed comparison. Later analytics must report scope and limitations rather than claim real-world causal elasticity from these fixtures. The generator contains no classifier or external decision API.

Known dirty fixtures are described in DATA_CONTRACT.md and recorded in injected_defects.csv. Acceptance measurements restore documented original values solely to verify the generator's coherent construction. This does not create a clean dataset or establish future cleaning rules.

## Execution evidence

Run `python -B tests/test_phase1_generator.py --dataset data/raw/phase1-v1` for full-size assertions. Retained outputs: `reports/phase1/acceptance.json`, `reports/phase1/reproducibility.json`, and `reports/phase1/source_preservation.txt`. These are Phase 1 generator evidence, not Spark jobs, model evaluation, or production analytics.

Executed gate on 2026-09-26: **PASS**. Two full-size generations produced identical manifests and hashes for all 12 CSV files (eleven entities plus injected_defects.csv). The repeat output was temporary and removed after comparison. Both overwrite-safety unit tests passed; their output is retained in `reports/phase1/unit_tests.txt`. All 15 original Phase 0 file hashes and Git HEAD/tree were unchanged.

| Measured fixture | Result |
|---|---:|
| Completed item-1 portions | 125,766 |
| Item-1 contribution | PKR -14,202,850 |
| Completed item-2 portions | 154 |
| Observed item-3 wasted/sold ratio | 0.70136 |
| Item-4 June contribution | PKR -249,290 |
| Largest synchronized item-13 feedback burst | 41 events |

These measurements use documented pre-injection values to verify generation. They are not a cleaned analytical release or deployed business report. Phase 1 ends here; Spark ingestion and later phases have not started.
