# DineIQ data dictionary

Dataset version: `phase1-v1`; cleaned analytical version: `phase1-v1-clean-v3`. All money is PKR, all quantities are menu portions, and timestamps represent Asia/Karachi. Synthetic IDs are stable only within this dataset version.

The [raw data contract](DATA_CONTRACT.md) defines every raw column, key, relationship, unit, date bound, generation rule, and deliberate dirty fixture. The table below maps those raw entities to the current processed and application layers.

| Raw entity | Grain / primary key | Current representation |
| --- | --- | --- |
| `Customers.csv` | Customer / `Customer_ID` | `customer_rfm.parquet`, `customer_segments.parquet`; no name in analytics API |
| `Menu_Categories.csv` | Category / `Category_ID` | `menu_categories` in SQLite and category references in clean sales |
| `Menu_Items.csv` | Item / `Item_ID` | `menu_items` in SQLite; all 150 items in `menu_metrics.parquet` |
| `Restaurants.csv` | Location / `Location_ID` | `restaurant_locations` in SQLite; `location_daily.parquet` |
| `Orders.csv` | Order / `Order_ID` | `orders_validated.parquet`; completed orders only in clean sales |
| `Order_Items.csv` | Line / `Order_Item_ID` | `sales.parquet`, one clean completed line per row |
| `Ratings.csv` | Rating / `Rating_ID` | `ratings.parquet` with valid 1–5 stars |
| `Wastage.csv` | Observed item/location/day / `Wastage_ID` | `wastage.parquet`; managed records separately in SQLite |
| `Inventory.csv` | Item/location period ledger / `Inventory_ID` | `inventory_records` in SQLite |
| `Pricing_History.csv` | Item/effective date / `Pricing_ID` | `pricing_history` in SQLite |
| `Promotions.csv` | Campaign / `Promotion_ID` | `promotions` in SQLite; `Promotion_ID` on sales |

## Core processed measures

| Field | Definition |
| --- | --- |
| `sales.Quantity` | Valid positive portions on a completed order line |
| `sales.Unit_Price` | Historical effective price per portion before discount |
| `sales.Discount_Applied` | Absolute discount for the full line, in PKR |
| `sales.Net_Revenue` | `Quantity × Unit_Price − Discount_Applied` |
| `sales.Cost_Total` | `Quantity × Cost` |
| `sales.Contribution` | `Net_Revenue − Cost_Total`; excludes overhead and wastage cost |
| `menu_metrics.Profit_Percent` | `100 × Contribution / Revenue` where revenue is positive |
| `customer_rfm.Recency_Days` | Days from snapshot to last completed order |
| `customer_rfm.Frequency` | Number of distinct completed `Order_ID`, not line count |
| `customer_rfm.Monetary` | Sum of clean net line revenue for that customer |
| `location_daily.Demand` | Sum of completed-sale portions per date/location |
| `wastage.Quantity_Wasted` | Observed wasted portions; missing item/location/days are not proven zero |
| `wastage.Cost_Impact` | Observed wasted portions × item cost |
| `customer_segments.Cluster` | KMeans numeric cluster from scaled log RFM |
| `customer_segments.Segment` | Business name assigned after cluster profiling |
| `wastage_next_week.Expected_Wastage` | Experimental next-week estimate for observed-record week subtotal, portions |
| `wastage_next_week.Risk` | Classifier-based risk flag; probability threshold chosen on prior validation data |

Raw counts: 100,080 order rows including 80 deliberate duplicate rows, 1,000,000 order lines, 50,000 customers, 150 items, 10 categories, and 20 locations. Current clean output has 99,970 validated unique orders, 96,010 completed orders, 959,964 completed sale lines, 49,960 valid wastage records, and 99,906 valid ratings. Clean sales are also partitioned into 20 location directories for Spark SQL. See `data/processed/phase1-v1/quality_report.json` and `partition_strategy.json` for machine-readable evidence.
