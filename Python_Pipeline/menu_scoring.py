"""Explainable, multifactor menu classification without synthetic target labels."""

import pandas as pd


RULE_VERSION = "menu-multifactor-v1"


def classify_items(items: pd.DataFrame) -> pd.DataFrame:
    result = items.copy()
    if result.empty:
        return result
    result["sales_percentile"] = result.sales.rank(pct=True)
    result["margin_percentile"] = result.profit_percent.rank(pct=True)
    result["wastage_percent"] = (100 * result.wastage_quantity /
        (result.sales + result.wastage_quantity).where((result.sales + result.wastage_quantity).ne(0))).fillna(0)
    result["repeat_purchase_rate"] = result.repeat_purchase_rate.fillna(0)
    result["sales_trend_percent"] = result.sales_trend_percent.fillna(0)
    result["Average_Rating"] = result.Average_Rating.fillna(0)
    result["Rating_Count"] = result.Rating_Count.fillna(0)
    result["promotion_dependency"] = result.promotion_dependency.fillna(0)
    result["insufficient_history"] = (result.active_days.lt(30) | result.orders.lt(20))
    result["evidence_score"] = (
        0.25 * result.sales_percentile + 0.25 * result.margin_percentile +
        0.12 * (result.Average_Rating / 5).clip(0, 1) +
        0.10 * result.repeat_purchase_rate.clip(0, 1) +
        0.10 * (1 - result.wastage_percent / 100).clip(0, 1) +
        0.10 * (1 - result.promotion_dependency).clip(0, 1) +
        0.08 * ((result.sales_trend_percent + 100) / 200).clip(0, 1)
    )

    def classify(row):
        high_volume = row.sales > 0 and row.sales_percentile >= .55
        healthy_margin = row.contribution > 0 and row.margin_percentile >= .5
        acceptable_waste = row.wastage_percent <= 15
        acceptable_rating = row.Rating_Count < 5 or row.Average_Rating >= 3.5
        stable_trend = row.sales_trend_percent >= -30
        low_promotion_dependence = row.promotion_dependency <= .35
        if high_volume and healthy_margin and acceptable_waste and acceptable_rating and stable_trend and low_promotion_dependence:
            return "Profit Driver"
        if high_volume:
            return "Volume Driver"
        promising_quality = row.Rating_Count >= 5 and row.Average_Rating >= 4
        if healthy_margin and acceptable_waste and (promising_quality or row.repeat_purchase_rate >= .2):
            return "Hidden Opportunity"
        return "Low Performer"

    result["classification"] = result.apply(classify, axis=1)
    result["classification_rule_version"] = RULE_VERSION
    result["classification_evidence"] = result.apply(lambda row: {
        "sales_percentile": round(float(row.sales_percentile), 4),
        "profit_percent": round(float(row.profit_percent), 2),
        "rating": round(float(row.Average_Rating), 2),
        "repeat_purchase_rate": round(float(row.repeat_purchase_rate), 4),
        "wastage_percent": round(float(row.wastage_percent), 2),
        "promotion_dependency": round(float(row.promotion_dependency), 4),
        "sales_trend_percent": round(float(row.sales_trend_percent), 2),
        "insufficient_history": bool(row.insufficient_history)}, axis=1)
    return result
