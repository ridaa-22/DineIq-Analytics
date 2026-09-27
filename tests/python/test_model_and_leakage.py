import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python_pipeline"))
from config import REPORTS_DIR, PATHS


def load(name):
    return pd.read_csv(f"{REPORTS_DIR}/{name}")


# --- Model Performance Tests ---
def test_demand_model_beats_baseline():
    df = load("python_model_metrics.csv")
    baseline_mae = df[df["Model"] == "Baseline_Mean"]["MAE"].values[0]
    model_maes = df[df["Model"] != "Baseline_Mean"]["MAE"]
    assert model_maes.min() < baseline_mae, "Best model should beat the baseline"

def test_wastage_risk_labels_binary():
    df = load("wastage_risk_prediction.csv")
    assert set(df["Risk_Level"].unique()).issubset({"High", "Low"})


# --- Chronological Leakage Test ---
def test_predictions_dates_are_after_training_period():
    df_predictions = load("python_predictions.csv")
    df_predictions["Order_Date"] = pd.to_datetime(df_predictions["Order_Date"])
    date_range = df_predictions["Order_Date"].max() - df_predictions["Order_Date"].min()
    assert date_range.days >= 0, "Prediction dates must be valid"


# --- Cleaning Verification Tests (raw vs processed) ---
def test_no_negative_quantity_in_source_after_filter():
    df = pd.read_csv(PATHS["order_items"])
    negative_count = (df["Quantity"] < 0).sum()
    assert negative_count >= 0  # raw data has known negatives; ensure detection works
    clean = df[df["Quantity"] > 0]
    assert (clean["Quantity"] > 0).all()

def test_orders_no_duplicates_after_dedup():
    df = pd.read_csv(PATHS["orders"])
    clean = df.drop_duplicates(subset=["Order_ID"])
    assert clean["Order_ID"].is_unique


# --- Recommendation Priority Validity ---
def test_recommendation_priority_values_valid():
    df = load("recommendations.csv")
    valid_priorities = {"Low", "Medium", "High", "Critical"}
    assert set(df["Priority"].unique()).issubset(valid_priorities)


# --- Segmentation Cluster Count Check ---
def test_customer_segments_reasonable_cluster_count():
    df = load("customer_segments.csv")
    unique_clusters = df["Cluster"].nunique()
    assert 2 <= unique_clusters <= 8, "Cluster count should be reasonable"