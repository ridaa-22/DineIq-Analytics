"""Evidence-based slow-moving assessment for global or location-scoped menu rows."""

import pandas as pd


RULE_VERSION = "slow-moving-multifactor-v1"
OUTPUT_COLUMNS = ["Location_ID", "Slow_Moving_Status", "Severity", "Evidence", "Reason",
                  "History_Status", "Recommended_Action", "Slow_Moving_Rule_Version"]


def analyze_slow_moving(items: pd.DataFrame) -> pd.DataFrame:
    """Assess an already-scoped menu summary; ranks are relative to each scope."""
    result = items.copy()
    if result.empty:
        for column in OUTPUT_COLUMNS:
            result[column] = pd.Series(dtype="object")
        return result
    if "Location_ID" not in result:
        result["Location_ID"] = None
    if "Scope" not in result:
        result["Scope"] = result.Location_ID.map(
            lambda value: "GLOBAL" if pd.isna(value) else f"LOCATION_{int(value)}")
    result["_scope"] = result.Scope
    result["_volume_pct"] = result.groupby("_scope").sales.rank(pct=True)
    result["_orders_per_30_days"] = 30 * result.orders / result.history_days.clip(lower=1)
    result["_frequency_pct"] = result.groupby("_scope")._orders_per_30_days.rank(pct=True)
    result["_margin_pct"] = result.groupby("_scope").profit_percent.rank(pct=True)

    def decide(row):
        history_days = int(row.history_days)
        recency = int(row.days_since_last_purchase)
        trend = float(row.sales_trend_percent)
        repeat = float(row.repeat_purchase_rate)
        waste = float(row.wastage_percent)
        low_volume = row["_volume_pct"] <= .35
        low_frequency = row["_frequency_pct"] <= .35
        declining = trend <= -20
        stale = recency >= 30
        weak_repeat = repeat <= .10
        weak_economics = row.contribution <= 0 or row["_margin_pct"] <= .35 or waste >= 15
        high_margin = row.contribution > 0 and row["_margin_pct"] >= .60
        quality_or_momentum = (row.Rating_Count >= 5 and row.Average_Rating >= 4) or trend >= 0 or repeat >= .15
        seasonal = history_days >= 180 and row.active_months >= 4 and row.seasonal_top3_share >= .70
        evidence = {
            "sales": int(row.sales), "volume_percentile": round(float(row["_volume_pct"]), 4),
            "orders": int(row.orders), "orders_per_30_days": round(float(row["_orders_per_30_days"]), 2),
            "order_frequency_percentile": round(float(row["_frequency_pct"]), 4),
            "days_since_last_purchase": recency, "recent_trend_percent": round(trend, 2),
            "repeat_purchase_rate": round(repeat, 4),
            "profit_percent": round(float(row.profit_percent), 2),
            "contribution": round(float(row.contribution), 2),
            "wastage_percent": round(waste, 2),
            "seasonal_top3_month_share": round(float(row.seasonal_top3_share), 4),
            "active_months": int(row.active_months), "history_days": history_days,
            "location_context": row.Scope,
            "global_sales": int(row.global_sales) if "global_sales" in row else None,
        }
        if history_days < 90:
            status, severity = "INSUFFICIENT_HISTORY", "UNDETERMINED"
            reason = "Fewer than 90 calendar days since introduction; demand pattern is immature."
            action = "Continue observing; review after at least 90 days of availability."
            history = "INSUFFICIENT"
        elif row.sales == 0:
            status, severity = "NO_OBSERVED_SALES", "REVIEW"
            reason = "No completed sales in this scope; local availability is not proven."
            action = "Verify listing, stock, and availability before judging demand."
            history = "ESTABLISHED"
        elif seasonal:
            status, severity = "SEASONAL_REVIEW", "REVIEW"
            reason = "At least 70% of volume falls in three months; one year cannot prove recurring seasonality."
            action = "Review seasonal timing and stock; avoid permanent removal from one off-season."
            history = "ESTABLISHED"
        elif low_volume and high_margin and quality_or_momentum:
            status, severity = "HIDDEN_OPPORTUNITY", "LOW"
            reason = "Low relative volume with healthy contribution and quality or positive demand momentum."
            action = "Test visibility and placement before reducing menu presence."
            history = "ESTABLISHED"
        elif low_volume and low_frequency and (declining or stale) and (weak_repeat or weak_economics):
            status = "SLOW_MOVER"
            severity = "HIGH" if recency >= 60 or trend <= -40 or waste >= 30 else "MEDIUM"
            reason = ("Low relative volume and order frequency with declining or stale demand, "
                      "plus weak repeats or economics.")
            action = "Review local menu placement, preparation, and stock; test changes before removal."
            history = "ESTABLISHED"
        elif low_volume and low_frequency and (weak_repeat or weak_economics):
            status, severity = "WATCHLIST", "LOW"
            reason = "Low relative volume and order frequency with weak repeats or economics; demand decline is unconfirmed."
            action = "Monitor trend, repeat purchasing, and waste before intervening."
            history = "ESTABLISHED"
        else:
            status, severity = "NOT_SLOW", "NONE"
            reason = "The combined slow-moving conditions are not met in this scope."
            action = "Continue normal monitoring."
            history = "ESTABLISHED"
        return {"Slow_Moving_Status": status, "Severity": severity, "Evidence": evidence,
                "Reason": reason, "History_Status": history, "Recommended_Action": action,
                "Slow_Moving_Rule_Version": RULE_VERSION}

    assessed = pd.DataFrame([decide(row) for _, row in result.iterrows()], index=result.index)
    return pd.concat([result.drop(columns=["_scope", "_volume_pct", "_orders_per_30_days",
                                           "_frequency_pct", "_margin_pct"]), assessed], axis=1)
