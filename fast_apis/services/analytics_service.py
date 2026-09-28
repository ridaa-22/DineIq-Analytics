"""Load only known, existing analytical reports. Values are provisional demo outputs."""

import csv
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"
MODELS_DIR = PROJECT_ROOT / "Models"

REPORTS = {
    "menu-intelligence": "menu_classification.csv",
    "customer-segments": "customer_segments.csv",
    "forecast": "python_predictions.csv",
    "model-comparison": "dual_pipeline_comparison.csv",
    "recommendations": "recommendations.csv",
}


def unavailable():
    return {"available": False, "message": "Analytics output has not been generated yet."}


def clean_value(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
        if not math.isfinite(number):
            return None
        return int(number) if number.is_integer() else number
    except (ValueError, TypeError):
        return value


@lru_cache(maxsize=32)
def rows(name):
    if name not in REPORTS.values() and name not in {
        "location_intelligence.csv", "python_model_metrics.csv", "spark_model_metrics.csv"
    }:
        raise ValueError("Report is not allow-listed")
    path = REPORTS_DIR / name
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8-sig") as source:
        return [{key: clean_value(value) for key, value in row.items()}
                for row in csv.DictReader(source)]


def page(data, limit, offset, **extra):
    return {"available": True, "total": len(data), "limit": limit, "offset": offset,
            "records": data[offset:offset + limit], **extra}


def get_executive_summary():
    menu = rows("menu_classification.csv")
    segments = rows("customer_segments.csv")
    locations = rows("location_intelligence.csv")
    recommendations = rows("recommendations.csv")
    comparison = rows("dual_pipeline_comparison.csv")
    if not any(data is not None for data in (menu, segments, locations, recommendations, comparison)):
        return unavailable()
    matches = sum(row.get("Match_Status") == "Close Match" for row in comparison or [])
    return {
        "available": True,
        "total_revenue": None,
        "average_order_value": None,
        "total_orders": sum(row.get("Total_Orders") or 0 for row in locations) if locations else None,
        "total_customers": None,
        "segmented_customers": len(segments) if segments is not None else None,
        "menu_items": len(menu) if menu is not None else None,
        "critical_recommendations": sum(row.get("Priority") == "Critical" for row in recommendations) if recommendations is not None else None,
        "comparison_cases": len(comparison) if comparison is not None else None,
        "reported_agreement_percentage": round(matches * 100 / len(comparison), 2) if comparison else None,
        "data_status": "Provisional legacy report outputs; analytics are not SRS validated.",
    }


def get_menu_intelligence(classification=None, limit=50, offset=0):
    data = rows("menu_classification.csv")
    if data is None:
        return unavailable()
    if classification:
        data = [row for row in data if row.get("Performance_Class", "").casefold() == classification.casefold()]
    return page(data, limit, offset, source="menu_classification.csv")


def get_customer_segments(limit=25, offset=0):
    data = rows("customer_segments.csv")
    if data is None:
        return unavailable()
    return page(data, limit, offset, summary=dict(Counter(row.get("Customer_Segment") or "Unlabeled" for row in data)),
                source="customer_segments.csv")


def get_forecast(limit=30, offset=0):
    data = rows("python_predictions.csv")
    if data is None:
        return unavailable()
    return page(data, limit, offset, scope="Global daily demand; historical holdout predictions, not future item forecasts",
                source="python_predictions.csv")


def get_model_comparison(limit=30, offset=0):
    data = rows("dual_pipeline_comparison.csv")
    if data is None:
        return unavailable()
    differences = [row["Numerical_Difference"] for row in data if isinstance(row.get("Numerical_Difference"), (int, float))]
    matches = sum(row.get("Match_Status") == "Close Match" for row in data)
    summary = {"case_count": len(data), "average_difference": round(sum(differences) / len(differences), 2) if differences else None,
               "reported_agreement_percentage": round(100 * matches / len(data), 2) if data else None,
               "srs_minimum_cases": 100,
               "note": "Existing report uses a median-difference match rule; agreement is provisional."}
    return page(data, limit, offset, summary=summary, source="dual_pipeline_comparison.csv")


def get_recommendations(priority=None, type=None, limit=30, offset=0):
    data = rows("recommendations.csv")
    if data is None:
        return unavailable()
    if priority:
        data = [row for row in data if row.get("Priority", "").casefold() == priority.casefold()]
    if type:
        data = [row for row in data if row.get("Type", "").casefold() == type.casefold()]
    return page(data, limit, offset, source="recommendations.csv")


def get_model_status():
    model_names = ["customer_kmeans.joblib", "customer_scaler.joblib", "demand_model.joblib", "wastage_risk_model.joblib"]
    python_models = [{"name": name, "available": (MODELS_DIR / "python" / name).is_file(), "model_version": None}
                     for name in model_names]
    spark_models = list((MODELS_DIR / "spark").rglob("metadata")) if (MODELS_DIR / "spark").is_dir() else []
    return {"available": True, "model_version": None, "python_models": python_models,
            "spark_model_available": bool(spark_models),
            "python_metrics": rows("python_model_metrics.csv"),
            "spark_metrics": rows("spark_model_metrics.csv"),
            "python_predictions_available": (REPORTS_DIR / "python_predictions.csv").is_file(),
            "spark_predictions_available": (REPORTS_DIR / "spark_predictions.csv").is_file(),
            "comparison_case_count": len(rows("dual_pipeline_comparison.csv") or []),
            "models_loaded_for_inference": False}


def download_path(report_name):
    filename = REPORTS.get(report_name)
    path = REPORTS_DIR / filename if filename else None
    return path if path is not None and path.is_file() else None
