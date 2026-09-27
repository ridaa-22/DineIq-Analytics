from pyspark.sql import SparkSession
from pyspark.sql.functions import col, dayofweek, month, dayofmonth, to_date, sum as spark_sum, lag
from pyspark.sql.window import Window
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression, RandomForestRegressor, GBTRegressor
from pyspark.ml.evaluation import RegressionEvaluator
import pandas as pd
from config import PATHS, REPORTS_DIR

spark = SparkSession.builder \
    .appName("DineIQ-Spark-Demand-Model") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

# 1. Data load karna
df_orders = spark.read.csv(PATHS["orders"], header=True, inferSchema=True)
df_order_items = spark.read.csv(PATHS["order_items"], header=True, inferSchema=True)

# 2. Cleaning
df_order_items = df_order_items.filter(col("Quantity") > 0)
df_orders = df_orders.dropDuplicates(["Order_ID"]).filter(col("Order_DateTime").isNotNull())
df_orders = df_orders.filter(col("Order_Status") == "Completed")
df_orders = df_orders.withColumn("Order_Date", to_date(col("Order_DateTime")))

# 3. Merge + daily demand
df_merged = df_order_items.join(df_orders.select("Order_ID", "Order_Date"), "Order_ID", "inner")
daily_demand = df_merged.groupBy("Order_Date").agg(spark_sum("Quantity").alias("Quantity")).orderBy("Order_Date")

# 4. Feature engineering (same as Python side)
daily_demand = daily_demand.withColumn("DayOfWeek", dayofweek(col("Order_Date")))
daily_demand = daily_demand.withColumn("Month", month(col("Order_Date")))
daily_demand = daily_demand.withColumn("Day", dayofmonth(col("Order_Date")))
daily_demand = daily_demand.withColumn("IsWeekend", (col("DayOfWeek").isin([1, 7])).cast("int"))

window_spec = Window.orderBy("Order_Date")
daily_demand = daily_demand.withColumn("Lag_1", lag("Quantity", 1).over(window_spec))
daily_demand = daily_demand.withColumn("Lag_7", lag("Quantity", 7).over(window_spec))
daily_demand = daily_demand.dropna()

# 5. Train/Test chronological split (80/20, same as Python side)
daily_pd = daily_demand.orderBy("Order_Date").toPandas()
split_idx = int(len(daily_pd) * 0.8)
train_dates = daily_pd.iloc[:split_idx]["Order_Date"].tolist()
test_dates = daily_pd.iloc[split_idx:]["Order_Date"].tolist()

train_df = daily_demand.filter(col("Order_Date").isin(train_dates))
test_df = daily_demand.filter(col("Order_Date").isin(test_dates))

# 6. Feature vector
feature_cols = ["DayOfWeek", "Month", "Day", "IsWeekend", "Lag_1", "Lag_7"]
assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
train_vec = assembler.transform(train_df)
test_vec = assembler.transform(test_df)

# 7. Baseline (mean of train)
baseline_value = train_df.agg({"Quantity": "avg"}).collect()[0][0]

# 8. Train 3 models
models = {
    "LinearRegression": LinearRegression(featuresCol="features", labelCol="Quantity"),
    "RandomForest": RandomForestRegressor(featuresCol="features", labelCol="Quantity", numTrees=100, seed=42),
    "GBTRegressor": GBTRegressor(featuresCol="features", labelCol="Quantity", seed=42)
}

evaluator_mae = RegressionEvaluator(labelCol="Quantity", predictionCol="prediction", metricName="mae")
evaluator_rmse = RegressionEvaluator(labelCol="Quantity", predictionCol="prediction", metricName="rmse")
evaluator_r2 = RegressionEvaluator(labelCol="Quantity", predictionCol="prediction", metricName="r2")

results = []
best_model, best_mae, best_name, best_predictions = None, float("inf"), None, None

for name, model in models.items():
    fitted = model.fit(train_vec)
    predictions = fitted.transform(test_vec)
    mae = evaluator_mae.evaluate(predictions)
    rmse = evaluator_rmse.evaluate(predictions)
    r2 = evaluator_r2.evaluate(predictions)
    results.append({"Model": name, "MAE": mae, "RMSE": rmse, "R2": r2})
    print(f"{name} -> MAE: {mae:.2f}, RMSE: {rmse:.2f}, R2: {r2:.3f}")
    if mae < best_mae:
        best_mae, best_model, best_name, best_predictions = mae, fitted, name, predictions

results.append({"Model": "Baseline_Mean", "MAE": abs(baseline_value - test_df.agg({"Quantity": "avg"}).collect()[0][0]), "RMSE": None, "R2": None})

# 9. Save metrics
pd.DataFrame(results).to_csv(f"{REPORTS_DIR}/spark_model_metrics.csv", index=False)

# 10. Save predictions
final_predictions = best_predictions.select(
    col("Order_Date"), col("Quantity").alias("Actual"), col("prediction").alias("Spark_Prediction")
).toPandas()
final_predictions.to_csv(f"{REPORTS_DIR}/spark_predictions.csv", index=False)

print(f"\nBest Spark Model: {best_name} | MAE: {best_mae:.2f}")
print("Spark Demand Model Complete!")

spark.stop()