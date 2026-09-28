"""Spark SQL over persisted, cleaned sales Parquet for reproducible aggregates."""

import csv
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "processed_spark"


def write_csv(path, dataframe):
    rows = dataframe.collect()
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=dataframe.columns)
        writer.writeheader()
        writer.writerows(row.asDict() for row in rows)
    return len(rows)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    spark = SparkSession.builder.appName("DineIQ Cleaned Spark SQL").master("local[2]").getOrCreate()
    spark.conf.set("spark.sql.session.timeZone", "Asia/Karachi")
    spark.sparkContext.setLogLevel("ERROR")
    try:
        partition_root = ROOT / "data" / "processed" / "phase1-v1" / "sales_by_location"
        files = sorted(partition_root.glob("Location_ID=*/part.parquet"))
        if not files:
            raise FileNotFoundError(f"No partitioned clean sales found in {partition_root}")
        # Exact file paths avoid a Hadoop directory listing that fails on this
        # Windows host without native winutils; basePath restores the partition.
        sales = spark.read.option("basePath", str(partition_root)).parquet(*(str(path) for path in files))
        sales.createOrReplaceTempView("completed_sales")
        menu = spark.sql("""SELECT Item_ID, first(Item_Name) AS Item_Name, sum(Quantity) AS Units,
            round(sum(Net_Revenue),2) AS Net_Revenue, round(sum(Contribution),2) AS Contribution,
            count(DISTINCT Order_ID) AS Orders FROM completed_sales GROUP BY Item_ID""")
        locations = spark.sql("""SELECT Location_ID, count(DISTINCT Order_ID) AS Orders,
            round(sum(Net_Revenue),2) AS Net_Revenue, round(sum(Contribution),2) AS Contribution
            FROM completed_sales GROUP BY Location_ID""")
        peaks = (sales.withColumn("Hour", F.hour("Order_DateTime"))
                 .groupBy("Location_ID", "Hour")
                 .agg(F.countDistinct("Order_ID").alias("Orders"), F.sum("Net_Revenue").alias("Net_Revenue")))
        print({"menu_rows": write_csv(OUT / "menu_sql.csv", menu),
               "location_rows": write_csv(OUT / "locations_sql.csv", locations),
               "peak_rows": write_csv(OUT / "peaks.csv", peaks)})
    finally:
        spark.stop()


if __name__ == "__main__":
    run()
