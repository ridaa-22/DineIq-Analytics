import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from config import PATHS, REPORTS_DIR, MODELS_DIR

df_orders = pd.read_csv(PATHS["orders"])
df_order_items = pd.read_csv(PATHS["order_items"])

df_order_items = df_order_items[df_order_items["Quantity"] > 0]
df_orders = df_orders.drop_duplicates(subset=["Order_ID"]).dropna(subset=["Order_DateTime"])
df_orders = df_orders[df_orders["Order_Status"] == "Completed"]
df_orders["Order_DateTime"] = pd.to_datetime(df_orders["Order_DateTime"])
df_orders["Order_Date"] = df_orders["Order_DateTime"].dt.date

df_merged = df_order_items.merge(df_orders[["Order_ID", "Order_Date"]], on="Order_ID", how="inner")

daily_demand = df_merged.groupby("Order_Date")["Quantity"].sum().reset_index()
daily_demand["Order_Date"] = pd.to_datetime(daily_demand["Order_Date"])
daily_demand = daily_demand.sort_values("Order_Date").reset_index(drop=True)

daily_demand["DayOfWeek"] = daily_demand["Order_Date"].dt.dayofweek
daily_demand["Month"] = daily_demand["Order_Date"].dt.month
daily_demand["Day"] = daily_demand["Order_Date"].dt.day
daily_demand["IsWeekend"] = daily_demand["DayOfWeek"].isin([5, 6]).astype(int)
daily_demand["Lag_1"] = daily_demand["Quantity"].shift(1)
daily_demand["Lag_7"] = daily_demand["Quantity"].shift(7)
daily_demand = daily_demand.dropna().reset_index(drop=True)

split_idx = int(len(daily_demand) * 0.8)
train = daily_demand.iloc[:split_idx]
test = daily_demand.iloc[split_idx:]

features = ["DayOfWeek", "Month", "Day", "IsWeekend", "Lag_1", "Lag_7"]
X_train, y_train = train[features], train["Quantity"]
X_test, y_test = test[features], test["Quantity"]

baseline_pred = np.full(len(y_test), y_train.mean())
baseline_mae = mean_absolute_error(y_test, baseline_pred)

models = {
    "LinearRegression": LinearRegression(),
    "RandomForest": RandomForestRegressor(n_estimators=100, random_state=42),
    "GradientBoosting": GradientBoostingRegressor(random_state=42)
}

results = []
best_model, best_mae, best_name = None, float("inf"), None

for name, model in models.items():
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    results.append({"Model": name, "MAE": mae, "RMSE": rmse, "R2": r2})
    if mae < best_mae:
        best_mae, best_model, best_name = mae, model, name

results.append({"Model": "Baseline_Mean", "MAE": baseline_mae, "RMSE": None, "R2": None})
df_results = pd.DataFrame(results)
df_results.to_csv(f"{REPORTS_DIR}/python_model_metrics.csv", index=False)

joblib.dump(best_model, f"{MODELS_DIR}/demand_model.joblib")

test_preds = best_model.predict(X_test)
df_predictions = test.copy()
df_predictions["Python_Prediction"] = test_preds
df_predictions["Python_Error"] = df_predictions["Quantity"] - df_predictions["Python_Prediction"]
df_predictions[["Order_Date", "Quantity", "Python_Prediction", "Python_Error"]].to_csv(
    f"{REPORTS_DIR}/python_predictions.csv", index=False
)

print("Best Model:", best_name, "| MAE:", best_mae, "| Baseline MAE:", baseline_mae)
print("Demand Forecasting Complete!")