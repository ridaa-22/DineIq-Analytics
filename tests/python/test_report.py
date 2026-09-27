import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python_pipeline"))
from config import REPORTS_DIR

def load(name):
    path = f"{REPORTS_DIR}/{name}"
    assert os.path.exists(path), f"{name} file missing"
    return pd.read_csv(path)


# --- Customer Segmentation Tests ---
def test_customer_segments_exist():
    df = load("customer_segments.csv")
    assert len(df) > 0

def test_customer_segments_no_negative_rfm():
    df = load("customer_segments.csv")
    assert (df["Recency"] >= 0).all()
    assert (df["Frequency"] >= 0).all()
    assert (df["Monetary"] >= 0).all()

def test_customer_segments_all_labeled():
    df = load("customer_segments.csv")
    assert df["Customer_Segment"].notna().all()


# --- Menu Intelligence Tests ---
def test_menu_classification_exist():
    df = load("menu_classification.csv")
    assert len(df) > 0

def test_menu_classification_valid_classes():
    df = load("menu_classification.csv")
    valid_classes = {"Profit Driver", "Volume Driver", "Hidden Opportunity", "Low Performer"}
    assert set(df["Performance_Class"].unique()).issubset(valid_classes)

def test_menu_no_negative_revenue():
    df = load("menu_classification.csv")
    assert (df["Total_Revenue"] >= 0).all()


# --- Demand Forecasting Tests ---
def test_python_predictions_exist():
    df = load("python_predictions.csv")
    assert len(df) > 0

def test_model_metrics_exist():
    df = load("python_model_metrics.csv")
    assert len(df) > 0
    assert "MAE" in df.columns


# --- Basket Analysis Tests ---
def test_basket_rules_valid_metrics():
    df = load("basket_rules.csv")
    if len(df) > 0:
        assert (df["support"] >= 0).all() and (df["support"] <= 1).all()
        assert (df["confidence"] >= 0).all() and (df["confidence"] <= 1).all()
        assert (df["lift"] >= 0).all()


# --- Wastage/Price/Promotion Tests ---
def test_wastage_no_negative():
    df = load("wastage_intelligence.csv")
    assert (df["Total_Wasted"] >= 0).all()

def test_price_sensitivity_labels():
    df = load("price_intelligence.csv")
    valid_labels = {"Highly Price Sensitive", "Moderately Price Sensitive", "Low Price Sensitivity"}
    assert set(df["Sensitivity"].unique()).issubset(valid_labels)


# --- Churn Tests ---
def test_churn_risk_labels():
    df = load("churn_risk.csv")
    assert set(df["Churn_Risk"].unique()).issubset({"High", "Low"})


# --- Recommendation Tests ---
def test_recommendations_have_evidence():
    df = load("recommendations.csv")
    assert df["Evidence"].notna().all()
    assert df["Priority"].notna().all()