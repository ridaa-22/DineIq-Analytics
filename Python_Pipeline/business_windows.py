"""Observed price and campaign window calculations; no causal inference claim."""

import pandas as pd


def sales_metrics(rows):
    orders = rows.Order_ID.nunique() if not rows.empty else 0
    return {"quantity": float(rows.Quantity.sum()), "net_revenue": float(rows.Net_Revenue.sum()),
            "contribution": float(rows.Contribution.sum()), "orders": int(orders),
            "aov": float(rows.Net_Revenue.sum() / orders) if orders else 0.0,
            "customers": int(rows.Customer_ID.nunique()) if not rows.empty else 0}


def promotion_trap(before, during):
    if before["orders"] == 0 or during["orders"] == 0:
        return None
    return bool(during["quantity"] > before["quantity"] and during["contribution"] < before["contribution"])


def sensitivity(price_before, price_after, demand_before, demand_after):
    if price_before <= 0 or demand_before <= 0:
        return "NOT VERIFIABLE"
    price_change = (price_after - price_before) / price_before
    demand_change = (demand_after - demand_before) / demand_before
    if abs(price_change) < .005:
        return "NOT VERIFIABLE"
    if price_change * demand_change >= 0:
        return "UNDETERMINED"
    elasticity = abs(demand_change / price_change)
    return "HIGH" if elasticity >= 1 else "MODERATE" if elasticity >= .5 else "LOW"
