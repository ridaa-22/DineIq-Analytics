"""Spark multi-table integration and SQL over the authoritative clean dataset."""

import csv
import json
from pathlib import Path

from pyspark import StorageLevel

from spark_jobs.ingest import create_spark, sha256

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "phase1-v1"
OUT = ROOT / "reports" / "processed_spark"
TABLES = {
    "clean_orders": "orders_validated", "clean_customers": "customers_validated",
    "clean_lines": "order_items_validated", "clean_menu": "menu_items_validated",
    "clean_categories": "menu_categories_validated", "clean_locations": "restaurant_locations_validated",
    "clean_promotions": "promotions_validated", "clean_prices": "pricing_history_validated",
    "clean_ratings": "ratings", "clean_inventory": "inventory_validated", "clean_wastage": "wastage",
}


def write_csv(path, frame):
    rows = frame.collect()
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=frame.columns)
        writer.writeheader()
        writer.writerows(row.asDict() for row in rows)
    return len(rows)


def register_sources(spark, data=DATA):
    data = Path(data)
    report = data / "quality_report.json"
    if not report.is_file():
        raise FileNotFoundError(f"Missing clean quality report: {report}")
    quality = json.loads(report.read_text(encoding="utf-8"))
    if quality.get("dataset_version") != "phase1-v1-clean-v3":
        raise ValueError("Unsupported clean dataset version")
    manifest_path = data / "spark_snapshot_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing Spark input manifest: {manifest_path}; run build_processed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files = {f"{name}.parquet" for name in TABLES.values()} | {"sales.parquet"}
    if manifest.get("dataset_version") != quality["dataset_version"] or set(manifest.get("files", {})) != expected_files:
        raise ValueError("Spark snapshot manifest version or file set differs from clean contract")
    for name, digest in manifest["files"].items():
        path = data / name
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"Spark snapshot hash mismatch or missing file: {path}")
    for view, name in TABLES.items():
        path = data / f"{name}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing clean input {path}; run build_processed")
        spark.read.parquet(str(path)).createOrReplaceTempView(view)
    spark.read.parquet(str(data / "sales.parquet")).createOrReplaceTempView("authoritative_sales")
    return quality


def build_views(spark):
    """Preaggregate one-to-many tables and rank effective prices before final line grain."""
    spark.sql("""CREATE OR REPLACE TEMP VIEW rating_by_item_location AS
        SELECT r.Item_ID,o.Location_ID,count(*) AS Rating_Count,avg(r.Stars) AS Average_Rating
        FROM clean_ratings r JOIN clean_orders o ON r.Order_ID=o.Order_ID
        GROUP BY r.Item_ID,o.Location_ID""")
    spark.sql("""CREATE OR REPLACE TEMP VIEW wastage_by_item_location AS
        SELECT Item_ID,Location_ID,sum(Quantity_Wasted) AS Wastage_Quantity,
        round(sum(Cost_Impact),2) AS Wastage_Cost FROM clean_wastage GROUP BY Item_ID,Location_ID""")
    spark.sql("""CREATE OR REPLACE TEMP VIEW inventory_latest AS
        SELECT Item_ID,Location_ID,Stock_Quantity,Reorder_Level FROM (
          SELECT Item_ID,Location_ID,Stock_Quantity,Reorder_Level,
          row_number() OVER (PARTITION BY Item_ID,Location_ID ORDER BY Period_End DESC,Inventory_ID DESC) rn
          FROM clean_inventory) WHERE rn=1""")
    spark.sql("""CREATE OR REPLACE TEMP VIEW integrated_base AS
        SELECT l.Order_Item_ID,l.Order_ID,l.Item_ID,o.Customer_ID,o.Location_ID,o.Order_DateTime,
        o.Channel,o.Promotion_ID,l.Quantity,l.Unit_Price,l.Discount_Applied,
        m.Item_Name,m.Category_ID,m.Cost,cat.Category_Name,c.Customer_Name,
        loc.Location_Name,loc.City,p.Promotion_Name,p.Discount_Percent,p.Start_Date,p.End_Date,
        p.Applicable_Item_ID,p.Applicable_Category_ID,r.Rating_Count,r.Average_Rating,
        i.Stock_Quantity,i.Reorder_Level,w.Wastage_Quantity,w.Wastage_Cost
        FROM clean_lines l
        JOIN clean_orders o ON l.Order_ID=o.Order_ID AND o.Order_Status='Completed'
        JOIN clean_customers c ON o.Customer_ID=c.Customer_ID
        JOIN clean_menu m ON l.Item_ID=m.Item_ID
        JOIN clean_categories cat ON m.Category_ID=cat.Category_ID
        JOIN clean_locations loc ON o.Location_ID=loc.Location_ID
        LEFT JOIN clean_promotions p ON o.Promotion_ID=p.Promotion_ID
        LEFT JOIN rating_by_item_location r ON l.Item_ID=r.Item_ID AND o.Location_ID=r.Location_ID
        LEFT JOIN inventory_latest i ON l.Item_ID=i.Item_ID AND o.Location_ID=i.Location_ID
        LEFT JOIN wastage_by_item_location w ON l.Item_ID=w.Item_ID AND o.Location_ID=w.Location_ID""")
    spark.sql("""CREATE OR REPLACE TEMP VIEW integrated_sales AS
        SELECT Order_Item_ID,Order_ID,Item_ID,Customer_ID,Location_ID,Order_DateTime,Channel,
        Promotion_ID,Quantity,Unit_Price,Discount_Applied,Item_Name,Category_ID,Cost,
        Category_Name,Customer_Name,Location_Name,City,Promotion_Name,Discount_Percent,
        Start_Date,End_Date,Applicable_Item_ID,Applicable_Category_ID,Rating_Count,
        Average_Rating,Stock_Quantity,Reorder_Level,Wastage_Quantity,Wastage_Cost,
        Effective_Price,Effective_Date,
        round(cast(Quantity AS DECIMAL(18,2))*cast(Unit_Price AS DECIMAL(18,2))
              -cast(Discount_Applied AS DECIMAL(18,2)),2) AS Net_Revenue,
        round(cast(Quantity AS DECIMAL(18,2))*cast(Cost AS DECIMAL(18,2)),2) AS Cost_Total,
        round(cast(Quantity AS DECIMAL(18,2))*(cast(Unit_Price AS DECIMAL(18,2))
              -cast(Cost AS DECIMAL(18,2)))-cast(Discount_Applied AS DECIMAL(18,2)),2) AS Contribution,
        hour(Order_DateTime) AS Local_Hour,cast(Order_DateTime AS DATE) AS Local_Date,
        CASE WHEN Promotion_ID IS NOT NULL AND cast(Order_DateTime AS DATE)
                  BETWEEN cast(Start_Date AS DATE) AND cast(End_Date AS DATE)
             AND (CASE WHEN Applicable_Item_ID IS NOT NULL THEN Item_ID=Applicable_Item_ID
                       WHEN Applicable_Category_ID IS NOT NULL THEN Category_ID=Applicable_Category_ID
                       ELSE true END)
             THEN true ELSE false END AS Campaign_Eligible
        FROM (SELECT b.*,ph.Price AS Effective_Price,ph.Effective_Date,
              row_number() OVER (PARTITION BY b.Order_Item_ID
                ORDER BY ph.Effective_Date DESC NULLS LAST,ph.Pricing_ID DESC NULLS LAST) rn
              FROM integrated_base b LEFT JOIN clean_prices ph
                ON b.Item_ID=ph.Item_ID AND cast(ph.Effective_Date AS DATE)<=cast(b.Order_DateTime AS DATE)) WHERE rn=1""")


QUERIES = {
    "menu_sql.csv": """SELECT Item_ID,first(Item_Name) Item_Name,sum(Quantity) Units,
        round(sum(Net_Revenue),2) Net_Revenue,round(sum(Cost_Total),2) Cost,
        round(sum(Contribution),2) Contribution,count(DISTINCT Order_ID) Orders,
        round(100*sum(Contribution)/nullif(sum(Net_Revenue),0),2) Profit_Percent
        FROM integrated_sales GROUP BY Item_ID ORDER BY Item_ID""",
    "locations_sql.csv": """SELECT Location_ID,first(Location_Name) Location_Name,
        count(DISTINCT Order_ID) Orders,round(sum(Net_Revenue),2) Net_Revenue,
        round(sum(Cost_Total),2) Cost,round(sum(Contribution),2) Contribution
        FROM integrated_sales GROUP BY Location_ID ORDER BY Location_ID""",
    "peaks.csv": """SELECT Location_ID,Local_Hour Hour,count(DISTINCT Order_ID) Orders,
        round(sum(Net_Revenue),2) Net_Revenue FROM integrated_sales
        GROUP BY Location_ID,Local_Hour ORDER BY Location_ID,Hour""",
    "categories_sql.csv": """SELECT Category_ID,first(Category_Name) Category_Name,sum(Quantity) Units,
        round(sum(Net_Revenue),2) Net_Revenue,round(sum(Contribution),2) Contribution
        FROM integrated_sales GROUP BY Category_ID ORDER BY Category_ID""",
    "campaigns_sql.csv": """SELECT cast(Promotion_ID AS BIGINT) Promotion_ID,first(Promotion_Name) Promotion_Name,
        count(DISTINCT Order_ID) Orders,sum(Quantity) Units,round(sum(Net_Revenue),2) Net_Revenue,
        round(sum(Contribution),2) Contribution FROM integrated_sales WHERE Campaign_Eligible=true
        GROUP BY Promotion_ID ORDER BY Promotion_ID""",
    "high_wastage_sql.csv": """SELECT Item_ID,Location_ID,first(Item_Name) Item_Name,
        max(Wastage_Quantity) Wastage_Quantity,max(Wastage_Cost) Wastage_Cost,
        max(Stock_Quantity) Stock_Quantity,max(Rating_Count) Rating_Count
        FROM integrated_sales WHERE Wastage_Quantity IS NOT NULL GROUP BY Item_ID,Location_ID
        ORDER BY Wastage_Cost DESC,Item_ID,Location_ID LIMIT 100""",
    "channels_sql.csv": """SELECT Channel,count(DISTINCT Order_ID) Orders,sum(Quantity) Units,
        round(sum(Net_Revenue),2) Net_Revenue,round(sum(Contribution),2) Contribution
        FROM integrated_sales GROUP BY Channel ORDER BY Channel""",
}


def validate(spark, quality):
    metrics = spark.sql("""SELECT count(*) rows,count(DISTINCT Order_Item_ID) distinct_lines,
        sum(cast(Net_Revenue AS DECIMAL(28,2))) net_revenue,
        sum(cast(Cost_Total AS DECIMAL(28,2))) cost,
        sum(cast(Contribution AS DECIMAL(28,2))) contribution,
        sum(CASE WHEN Effective_Price IS NULL THEN 1 ELSE 0 END) missing_price,
        sum(CASE WHEN abs(cast(Effective_Price AS DOUBLE)-cast(Unit_Price AS DOUBLE))>0.01 THEN 1 ELSE 0 END) price_mismatch,
        sum(CASE WHEN Promotion_ID IS NOT NULL AND Promotion_Name IS NULL THEN 1 ELSE 0 END) missing_promotion,
        sum(CASE WHEN Category_Name IS NULL OR Location_Name IS NULL THEN 1 ELSE 0 END) missing_dimension
        FROM integrated_sales""").first().asDict()
    authority = spark.sql("""SELECT count(*) rows,round(sum(Net_Revenue),2) net_revenue,
        round(sum(Cost_Total),2) cost,round(sum(Contribution),2) contribution
        FROM authoritative_sales""").first().asDict()
    if metrics["rows"] != quality["clean_completed_lines"] or metrics["rows"] != authority["rows"]:
        raise ValueError(f"Spark join rows {metrics['rows']} disagree with clean sales {authority['rows']}")
    if metrics["distinct_lines"] != metrics["rows"]:
        raise ValueError("Spark joins multiplied Order_Item_ID grain")
    if any(metrics[key] for key in ("missing_price", "price_mismatch", "missing_promotion", "missing_dimension")):
        raise ValueError(f"Spark relationship/effective-price integrity failed: {metrics}")
    for key in ("net_revenue", "cost", "contribution"):
        if abs(float(metrics[key]) - float(authority[key])) > .05:
            raise ValueError(f"Spark {key} differs from clean sales")
    return {"dataset_version": quality["dataset_version"], "joined_rows": metrics["rows"],
            "distinct_order_item_ids": metrics["distinct_lines"],
            "financial_totals": {key: float(metrics[key]) for key in ("net_revenue", "cost", "contribution")},
            "authoritative_totals": {key: float(authority[key]) for key in ("net_revenue", "cost", "contribution")},
            "missing_price": metrics["missing_price"], "price_mismatch": metrics["price_mismatch"],
            "missing_promotion": metrics["missing_promotion"], "missing_dimension": metrics["missing_dimension"]}


def run(data=DATA, out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    spark = create_spark("DineIQ-Clean-Multi-Table-SQL")
    try:
        quality = register_sources(spark, data)
        build_views(spark)
        integrated = spark.table("integrated_sales").persist(StorageLevel.MEMORY_AND_DISK)
        integrated.count()
        result = validate(spark, quality)
        result["outputs"] = {name: write_csv(out / name, spark.sql(query)) for name, query in QUERIES.items()}
        (out / "integration_validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        integrated.unpersist()
    finally:
        spark.stop()


if __name__ == "__main__":
    run()
