# DineIQ Phase 1 data contract

Contract version: `phase1-v1`. Scope: synthetic raw generation and its acceptance fixtures only. Spark ingestion, quality jobs, cleaning, processed Parquet, features, and ML are later phases.

## Provenance and execution

The project root is the existing `DineIq-Analytics/` Git root. `Dineiq_Dataset_RM/`, the historical notebook, and the Phase 0 hash baseline remain untouched. The standalone generator reuses the legacy table scaffold and IDs rather than executing notebook cells or installing dependencies. It preserves all 50,000 customer, 100,000 order, 1,000,000 line, 150 menu, 10 category, and 20 location IDs. Ratings and wastage preserve their 1–100,000 / 1–50,000 ID ranges; pricing event meaning changes and is version-specific. Original 2,000 inventory IDs retain their item-location pairs; 1,000 additional pairs receive new IDs for complete coverage. Non-key synthetic attributes and transaction assignments may change to implement the scenarios.

Python 3.13 standard library is sufficient; no Pandas, Java, Spark, or Faker installation is required. Run from the project root:

```powershell
python -B data_generator/generate_phase1.py
python -B tests/test_phase1_generator.py
python -B tests/test_phase1_generator.py --dataset data/raw/phase1-v1
python -B tests/run_phase1_acceptance.py
```

Default output: `data/raw/phase1-v1/`. An existing output directory is refused, including an empty directory. For reproducibility checks use `--output` with a new separate directory and compare the CSV hashes and manifest. Failed/interrupted outputs are incomplete; do not consume them. Completion requires a manifest and a passing acceptance check. Changing the seed or generator produces another dataset realization; do not overwrite this version or mix its files with the historical snapshot.

`manifest.json` records seed, fixed bounds, all source-file SHA-256 values, generator SHA-256, output hashes/sizes/counts, currency, timezone, and injection count. It contains no wall-clock timestamp or output-directory-dependent field, so same inputs/source/seed produce identical content. Its dataset version identifies this generator contract, not a claim that differing seeds share identical records.

CSV encoding: UTF-8, header, comma delimiter, LF record terminator, standard CSV quoting. Empty string is null. IDs are positive integer identifiers; serialize without floating-point notation. Numeric quantities count menu-item portions, not kilograms or currency. Monetary fields use PKR decimal amounts with two decimal places. Computation uses integer paisa and half-up rounding. No taxes, delivery fees, or channel commissions are modeled; contribution is food/preparation contribution, not total business net profit.

## Time and status rules

- Timezone: Asia/Karachi, explicitly serialized `+05:00` on timestamps. Dates represent that local calendar date.
- Transaction bounds are inclusive: `2025-01-01T00:00:00+05:00` through `2026-01-01T00:00:00+05:00`. Orders 1 and 100000 anchor both endpoints. No current-time calls are used.
- Signup/opening dates must be on or before the order date. Ratings occur after the referenced completed order; they may extend up to 48 hours beyond transaction history. The deliberate rating burst is also after its orders.
- New item 9 is introduced 2025-12-01 and has no earlier lines.
- Order statuses: `Completed`, `Cancelled`. Preserve cancellations in raw data; future completed-sales KPIs exclude them. Cancellation lines and campaigns describe abandoned order contents, not realized demand or discounts.
- Channels: `Dine-in`, `Takeaway`, `Website`, `App`, `Third-Party Delivery`.
- `Is_Available`: 0/1. Generated master items are available; Introduced_Date separately controls historical availability.

## Table grains, keys, fields, and units

Except documented injected defects, primary keys are unique and non-null. Required foreign keys resolve. Each listed field is non-null except Orders.Promotion_ID and declared injection cases. Text names/descriptions/addresses remain synthetic legacy attributes. The contract does not interpret generated evidence as real restaurant findings.

| Table | Grain / PK | Foreign keys |
|---|---|---|
| Customers | One synthetic profile / Customer_ID | None |
| Menu_Categories | One category / Category_ID | None |
| Menu_Items | One item / Item_ID | Category_ID → Menu_Categories |
| Restaurants | One location / Location_ID | None |
| Promotions | One item-targeted campaign / Promotion_ID | Applicable_Item_ID → Menu_Items; Applicable_Category_ID → Menu_Categories and must match that item's category |
| Orders | One order header / Order_ID | Customer_ID, Location_ID; nullable Promotion_ID |
| Order_Items | One order line / Order_Item_ID | Order_ID → Orders; Item_ID → Menu_Items |
| Pricing_History | One item effective-price event / Pricing_ID; unique (Item_ID, Effective_Date) | Item_ID |
| Ratings | One feedback event / Rating_ID | Order_ID, Item_ID, Customer_ID; customer must own order, item must occur in order |
| Wastage | One observed preparation/wastage day / Wastage_ID; unique (Wastage_Date, Item_ID, Location_ID) | Item_ID, Location_ID |
| Inventory | One item-location period stock ledger / Inventory_ID; unique (Item_ID, Location_ID) | Item_ID, Location_ID |

| Table | Exact field definitions |
|---|---|
| Customers | Customer_ID: integer PK; Customer_Name: synthetic text; City: text; Signup_Date: ISO date; Preferred_Channel: stated synthetic preference, not a calculated behavioral feature |
| Menu_Categories | Category_ID: integer PK; Category_Name: text |
| Menu_Items | Item_ID: integer PK; Item_Name: text; Category_ID: integer FK; Base_Price: initial Jan 1 list price, PKR; Cost: per-portion preparation cost, PKR, constant during this version; Description: text; Is_Available: 0/1; Introduced_Date: first permitted order date |
| Restaurants | Location_ID: integer PK; Location_Name, City, Address: synthetic text; Opening_Date: ISO date |
| Promotions | Promotion_ID: integer PK; Promotion_Name: text; Discount_Percent: integer percent 0–100; Start_Date/End_Date: inclusive local ISO dates; Applicable_Category_ID/Applicable_Item_ID: integer FKs defining eligibility |
| Orders | Order_ID, Customer_ID, Location_ID: integer IDs; Order_DateTime: offset ISO timestamp; Channel: enum above; Promotion_ID: nullable integer FK; Order_Status: enum above |
| Order_Items | Order_Item_ID, Order_ID, Item_ID: integer IDs; Quantity: positive integer portions before fixture injection; Unit_Price: effective undiscounted per-portion price, PKR; Discount_Applied: absolute PKR discount for the entire line, not a percent or per-unit amount |
| Pricing_History | Pricing_ID, Item_ID: integers; Price: positive per-portion list price, PKR; Effective_Date: inclusive ISO date; latest event at/before transaction date sets Unit_Price |
| Ratings | Rating_ID, Order_ID, Item_ID, Customer_ID: integers; Stars: integer 1–5 before fixture injection; Rating_Date: offset timestamp; repeated feedback events on a purchased pair are allowed as an explicit synthetic feedback/anomaly fixture, not unique customer satisfaction observations |
| Wastage | Wastage_ID, Item_ID, Location_ID: integers; Wastage_Date: ISO date; Quantity_Wasted: integer portions; Cost_Impact: PKR at item Cost × wasted portions; Reason: Overproduction in this version; Demand_Quantity: completed sold portions that day; Quantity_Consumed: portions consumed to fulfill that demand; Prepared_Quantity: consumed + wasted portions |
| Inventory | Inventory_ID, Item_ID, Location_ID: integers; Stock_Quantity: closing portions; Reorder_Level: portion threshold; Last_Restocked_Date: final ledger date, not daily restock history; Opening_Stock, Received_Quantity, Consumed_Quantity, Wasted_Quantity: nonnegative integer portions over Period_Start/Period_End inclusive; period dates: ISO dates |

## Business relationships and economics

Campaigns apply only inside their date interval and to their designated item/category. An item target takes precedence over its category field; the category never expands an item-specific campaign. See [the campaign and time contract](PROMOTION_TIME_CONTRACT.md) for category, global, and location scope. Every campaign-bearing order contains at least one eligible item. Other items may share its basket; only eligible lines receive its percent discount. There are no unrelated random discounts. Discount amount is half-up rounded `Quantity × Unit_Price × Discount_Percent / 100` once per line. Zero discount on ineligible lines is expected.

Price history has two events per item, Jan 1 and Jul 1. Equal prices are valid historical observations; item 6 increases 40% on Jul 1. Base_Price is the initial list price, not a substitute for time-effective history. Unit_Price follows the history even when a deliberately invalid Base_Price is injected into the master fixture.

Future completed-sales calculations: gross revenue = quantity × unit price; net revenue = gross − absolute line discount; preparation cost = quantity × per-portion Cost; contribution = net revenue − preparation cost; contribution percentage = contribution / net revenue × 100 when net revenue > 0, otherwise undefined. Wastage cost is separately attributable operational loss; do not silently subtract it twice or call contribution full net profit. Some valid prices are below Cost intentionally; a loss is not an invalid transaction.

Wastage covers 50,000 sampled positive-demand item-location-days, including all observed item-3 days. Prepared = consumed + wasted; Cost_Impact is not an independent random number. Days absent from Wastage are outside the generated observation sample, not proven zero-waste days. Inventory is a period ledger, not a daily event stream; it reconciles generated completed consumption and observed wastage. Opening + received − consumed − wasted = closing. Do not join its period totals to each transaction and then sum them.

## Explicit dirty-data fixtures

The generator first constructs coherent relationships, then injects known defects. `injected_defects.csv` has Entity, Record_ID, Field, Rule, Original_Value, Injected_Value. It is generator test provenance, not quarantine or a cleaning-decision report. Original values allow acceptance tests to verify the underlying synthetic construction; later cleaning must implement independently documented policies and must not simply replace records from this answer key.

| Injection rule | Count / behavior |
|---|---|
| NEGATIVE_QUANTITY | 150 line quantities set to -1; original quantities/discounts retained in injection evidence |
| MISSING_NAME | 120 customer names blanked |
| MISSING_DATE | 30 order timestamps blanked, excluding endpoint anchors |
| INVALID_BASE_PRICE | 5 master initial prices set to -1.00; effective history remains valid |
| INVALID_STARS | 60 ratings set to 8 |
| NEGATIVE_WASTAGE | 40 observed wasted quantities set to -5; coherent original balance recorded |
| DUPLICATE_ROW | 40 customer and 80 order rows appended exactly; IDs unchanged |

Blank Promotion_ID is a legitimate no-campaign value. Defect counts refer to distinct injected cases; duplicated rows may repeat an already injected defect. No undeclared orphan, unpurchased rating, out-of-period campaign, pre-signup order, or pre-opening order is deliberately introduced.

## Acceptance boundary

The generator acceptance check verifies scale, declared errors, purchase-linked ratings, campaign applicability, effective prices, dates, inventory/preparation balances, and measurable scenarios described in [business_scenarios.md](business_scenarios.md). It assesses generation, not trained predictions or cleaned storage. Two full generations must match hashes for reproducibility. Original Phase 0 hashes must still pass. Results are retained in `reports/phase1/` after execution.

No menu labels are generated from a trivial sales rule. Scenario IDs and injection originals are evaluator fixtures and must never be passed to a model as predictive features. Inferred business classes, chronology/splits, processed Parquet, and all Spark work remain outside Phase 1.
