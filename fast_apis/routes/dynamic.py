"""Scoped analytical APIs backed by cleaned Parquet and independently trained models."""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
import joblib
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from fast_apis import database
from fast_apis.services import auth_service as auth
from fast_apis.services.analytics_filters import checked_filters
from Python_Pipeline.menu_scoring import classify_items
from Python_Pipeline.slow_moving import analyze_slow_moving
from Python_Pipeline.train_customer_segments import features as rfm_features
from Python_Pipeline.business_windows import promotion_trap, sales_metrics, sensitivity
from Python_Pipeline.business_time import local_dates, local_day_start, local_day_after, parse_order_timestamps
from Python_Pipeline.campaign_eligibility import get_eligible_sales_for_promotion
from Python_Pipeline.forecast_features import recursive_forecast

router = APIRouter(prefix="/api")
DATA = database.PROJECT_ROOT / "data" / "processed" / "phase1-v1"
MODELS = database.PROJECT_ROOT / "Models" / "integrated"


@lru_cache(maxsize=12)
def frame(name):
    path = DATA / f"{name}.parquet"
    if not path.is_file():
        raise HTTPException(503, f"Processed {name} data unavailable; run build_processed")
    try:
        return pd.read_parquet(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, f"Processed {name} data unavailable") from exc


def wastage_frame():
    """Combine immutable clean history with current, audited managed additions."""
    clean = frame("wastage")
    with database.connection() as db:
        managed = [dict(row) for row in db.execute("""SELECT id,item_id,location_id,wastage_date,
            quantity_wasted,cost_impact,reason FROM wastage_overrides""")]
    if not managed:
        return clean
    overlay = pd.DataFrame(managed).rename(columns={
        "id": "Wastage_ID", "item_id": "Item_ID", "location_id": "Location_ID",
        "wastage_date": "Wastage_Date", "quantity_wasted": "Quantity_Wasted",
        "cost_impact": "Cost_Impact", "reason": "Reason"})
    overlay["Wastage_ID"] = -overlay.Wastage_ID
    overlay["Wastage_Date"] = pd.to_datetime(overlay.Wastage_Date)
    return pd.concat([clean, overlay], ignore_index=True)


def records(value):
    return json.loads(value.to_json(orient="records", date_format="iso"))


def include_unsold_menu_items(grouped, category_id=None):
    """Expose newly managed items with provisional zero-history classification."""
    with database.connection() as db:
        catalog = pd.DataFrame([dict(row) for row in db.execute(
            "SELECT item_id,item_name,category_id FROM menu_items")])
    if catalog.empty:
        return grouped
    if category_id is not None:
        catalog = catalog[catalog.category_id.eq(category_id)]
    historical_ids = set(frame("sales").Item_ID.unique())
    missing = catalog[~catalog.item_id.isin(historical_ids)]
    if missing.empty:
        return grouped
    rows = missing.rename(columns={"item_id": "Item_ID", "item_name": "Item_Name",
                                   "category_id": "Category_ID"})
    for field in ("sales", "revenue", "cost", "contribution", "orders", "customers",
                  "discount", "profit_percent", "promotion_dependency", "active_days",
                  "repeat_purchase_rate", "sales_trend_percent", "wastage_quantity",
                  "wastage_cost", "Average_Rating", "Rating_Count"):
        rows[field] = 0.0
    return pd.concat([grouped, rows], ignore_index=True)


def add_slow_moving_evidence(grouped, sales, user, location_id):
    """Use the same clean sales scope as Menu Intelligence and one global snapshot date."""
    snapshot = pd.Timestamp(frame("sales").Date.max())
    catalog = frame("menu_items_validated")[["Item_ID", "Introduced_Date"]]
    introduced = pd.to_datetime(catalog.set_index("Item_ID").Introduced_Date)
    allowed = scope(user, location_id)
    effective_location = location_id if location_id is not None else (allowed[0] if allowed and len(allowed) == 1 else None)
    grouped = grouped.copy()
    first_known = pd.to_datetime(grouped.Item_ID.map(introduced))
    if effective_location is not None:
        locations = frame("restaurant_locations_validated")
        opening = locations.loc[locations.Location_ID.eq(effective_location), "Opening_Date"]
        if not opening.empty:
            first_known = first_known.clip(lower=pd.Timestamp(opening.iloc[0]))
    grouped["history_days"] = ((snapshot - first_known).dt.days + 1).fillna(0).clip(lower=0).astype(int)
    last_sale = grouped["last_sale"] if "last_sale" in grouped else pd.Series(pd.NaT, index=grouped.index)
    last_day = pd.to_datetime(last_sale, utc=True).dt.tz_convert("Asia/Karachi").dt.tz_localize(None).dt.normalize()
    grouped["days_since_last_purchase"] = (snapshot - last_day).dt.days.fillna(grouped.history_days).clip(lower=0).astype(int)
    if sales.empty:
        grouped["active_months"] = 0
        grouped["seasonal_top3_share"] = 0.0
    else:
        monthly = sales.groupby(["Item_ID", pd.to_datetime(sales.Date).dt.month]).Quantity.sum()
        active_months = monthly.groupby(level=0).size()
        concentration = monthly.groupby(level=0).apply(lambda values: values.nlargest(3).sum() / values.sum())
        grouped["active_months"] = grouped.Item_ID.map(active_months).fillna(0).astype(int)
        grouped["seasonal_top3_share"] = grouped.Item_ID.map(concentration).fillna(0.0)
    grouped["Location_ID"] = effective_location
    grouped["Scope"] = (f"LOCATION_{effective_location}" if effective_location is not None else
                        "GLOBAL" if allowed is None else "ASSIGNED_LOCATIONS")
    global_sales = frame("sales").groupby("Item_ID").Quantity.sum()
    grouped["global_sales"] = grouped.Item_ID.map(global_sales).fillna(0).astype(int)
    return analyze_slow_moving(grouped)


def scope(user, location_id):
    allowed = auth.allowed_location(user, location_id)
    if isinstance(allowed, list):
        return allowed
    return [allowed] if allowed is not None else None


def sales_for(user, location_id=None, date_from=None, date_to=None, item_id=None,
              category_id=None, channel=None, promotion_id=None):
    sales = frame("sales")
    locations = scope(user, location_id)
    if locations is not None:
        sales = sales[sales.Location_ID.isin(locations)]
    if date_from or date_to:
        dates = local_dates(sales.Order_DateTime)
        if date_from:
            sales = sales[dates.ge(date.fromisoformat(str(date_from)))]
            dates = dates.loc[sales.index]
        if date_to:
            sales = sales[dates.le(date.fromisoformat(str(date_to)))]
    if item_id is not None:
        sales = sales[sales.Item_ID.eq(item_id)]
    if category_id is not None:
        sales = sales[sales.Category_ID.eq(category_id)]
    if channel is not None:
        sales = sales[sales.Channel.eq(channel)]
    if promotion_id is not None:
        with database.connection() as db:
            campaign = db.execute("SELECT * FROM promotions WHERE promotion_id=?", (promotion_id,)).fetchone()
        if campaign is None:
            raise HTTPException(404, "Promotion not found")
        sales = get_eligible_sales_for_promotion(sales, dict(campaign), during=True)
    return sales


@router.get("/analytics/orders")
def orders(location_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
           channel: str | None = None, status: str | None = None,
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
           user=Depends(auth.current_user)):
    source = frame("orders_validated")
    allowed = scope(user, location_id)
    if allowed is not None:
        source = source[source.Location_ID.isin(allowed)]
    dates = local_dates(source.Order_DateTime)
    if date_from is not None:
        source = source[dates.ge(date_from)]
        dates = dates.loc[source.index]
    if date_to is not None:
        source = source[dates.le(date_to)]
    if channel:
        source = source[source.Channel.eq(channel)]
    if status:
        source = source[source.Order_Status.eq(status)]
    totals = frame("order_totals")[["Order_ID", "Net_Revenue"]]
    page = source.sort_values("Order_DateTime", ascending=False).iloc[offset:offset + limit]
    page = page.merge(totals, on="Order_ID", how="left", validate="one_to_one")
    return {"total": len(source), "orders": records(page),
            "status_counts": source.Order_Status.value_counts().to_dict(),
            "revenue_note": "Net revenue is shown only for completed orders with eligible clean lines; cancelled orders have no sales revenue.",
            "dataset_version": "phase1-v1-clean-v3"}


@router.get("/dashboard/executive")
def executive(location_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
              item_id: int | None = None, category_id: int | None = None,
              channel: str | None = None, promotion_id: int | None = None,
              user=Depends(auth.current_user)):
    filters = checked_filters("dashboard", location_id=location_id, date_from=date_from,
        date_to=date_to, item_id=item_id, category_id=category_id, channel=channel,
        promotion_id=promotion_id)
    sales = sales_for(user, **filters.model_dump(exclude_none=True))
    if sales.empty:
        return {"dataset_version": "phase1-v1-clean-v3", "orders": 0, "revenue": 0, "contribution": 0}
    order_counts = sales.groupby("Customer_ID").Order_ID.nunique()
    orders = sales.Order_ID.nunique()
    wastage = wastage_frame()
    allowed = scope(user, location_id)
    if allowed is not None:
        wastage = wastage[wastage.Location_ID.isin(allowed)]
    if date_from:
        wastage = wastage[wastage.Wastage_Date.ge(pd.Timestamp(date_from))]
    if date_to:
        wastage = wastage[wastage.Wastage_Date.le(pd.Timestamp(date_to))]
    if item_id is not None:
        wastage = wastage[wastage.Item_ID.eq(item_id)]
    if category_id is not None:
        items = frame("menu_items_validated")
        wastage = wastage[wastage.Item_ID.isin(items.loc[items.Category_ID.eq(category_id), "Item_ID"])]
    return {"dataset_version": "phase1-v1-clean-v3", "orders": int(orders),
            "revenue": round(float(sales.Net_Revenue.sum()), 2),
            "contribution": round(float(sales.Contribution.sum()), 2),
            "aov": round(float(sales.Net_Revenue.sum() / orders), 2),
            "active_customers": int(sales.Customer_ID.nunique()),
            "repeat_customers": int(order_counts.gt(1).sum()),
            "wastage_cost": round(float(wastage.Cost_Impact.sum()), 2),
            "filters": {"location_id": location_id, "date_from": date_from, "date_to": date_to}}


@router.get("/analytics/menu")
def menu(location_id: int | None = None, category_id: int | None = None, classification: str | None = None,
         date_from: date | None = None, date_to: date | None = None, item_id: int | None = None,
         channel: str | None = None, promotion_id: int | None = None,
         performance_class: str | None = None, rating: float | None = None,
         slow_status: str | None = None,
         limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    if classification and performance_class and classification != performance_class:
        raise HTTPException(422, "Conflicting performance classes")
    filters = checked_filters("menu", location_id=location_id, category_id=category_id,
        date_from=date_from, date_to=date_to, item_id=item_id, channel=channel,
        promotion_id=promotion_id, performance_class=performance_class or classification,
        rating=rating, slow_status=slow_status)
    sales = sales_for(user, location_id=location_id, date_from=date_from, date_to=date_to,
        channel=channel, promotion_id=promotion_id)
    classification = filters.performance_class
    def selected(grouped):
        if category_id is not None:
            grouped = grouped[grouped.Category_ID.eq(category_id)]
        if item_id is not None:
            grouped = grouped[grouped.Item_ID.eq(item_id)]
        if classification:
            grouped = grouped[grouped.classification.eq(classification)]
        if rating is not None:
            grouped = grouped[grouped.Average_Rating.ge(rating)]
        if slow_status is not None:
            grouped = grouped[grouped.Slow_Moving_Status.eq(slow_status)]
        return grouped
    if sales.empty:
        grouped = include_unsold_menu_items(pd.DataFrame())
        if grouped.empty:
            return {"total": 0, "items": [],
                    "method": "No observed sales in the selected scope or period"}
        grouped = classify_items(grouped)
        grouped = add_slow_moving_evidence(grouped, sales, user, location_id)
        grouped = selected(grouped)
        return {"total": len(grouped), "items": records(grouped.iloc[offset:offset + limit]),
                "method": "Multifactor descriptive classes and slow-moving evidence; zero-history items are provisional"}
    grouped = sales.groupby(["Item_ID", "Item_Name", "Category_ID"], as_index=False).agg(
        sales=("Quantity", "sum"), revenue=("Net_Revenue", "sum"), cost=("Cost_Total", "sum"),
        contribution=("Contribution", "sum"), orders=("Order_ID", "nunique"),
        customers=("Customer_ID", "nunique"), discount=("Discount_Applied", "sum"),
        first_sale=("Order_DateTime", "min"), last_sale=("Order_DateTime", "max"))
    grouped["profit_percent"] = (100 * grouped.contribution / grouped.revenue.where(grouped.revenue.ne(0))).fillna(0)
    grouped["promotion_dependency"] = grouped.discount / (grouped.revenue + grouped.discount).where((grouped.revenue + grouped.discount).ne(0))
    grouped["promotion_dependency"] = grouped.promotion_dependency.fillna(0)
    grouped["active_days"] = (grouped.last_sale - grouped.first_sale).dt.days
    purchases = sales.groupby(["Item_ID", "Customer_ID"]).Order_ID.nunique().reset_index(name="purchase_orders")
    repeat = purchases.groupby("Item_ID").purchase_orders.agg(lambda x: float(x.gt(1).mean())).reset_index().rename(
        columns={"purchase_orders": "repeat_purchase_rate"})
    grouped = grouped.merge(repeat, on="Item_ID", how="left")
    end = frame("sales").Order_DateTime.max()
    current = sales[sales.Order_DateTime.gt(end - pd.Timedelta(days=30))].groupby("Item_ID").Quantity.sum()
    previous = sales[sales.Order_DateTime.le(end - pd.Timedelta(days=30)) &
                     sales.Order_DateTime.gt(end - pd.Timedelta(days=60))].groupby("Item_ID").Quantity.sum()
    grouped["sales_trend_percent"] = grouped.Item_ID.map(
        lambda item: float(100 * (current.get(item, 0) - previous.get(item, 0)) / max(previous.get(item, 0), 1)))
    waste = wastage_frame()
    allowed = scope(user, location_id)
    if allowed is not None:
        waste = waste[waste.Location_ID.isin(allowed)]
    grouped = grouped.merge(waste.groupby("Item_ID").agg(wastage_quantity=("Quantity_Wasted", "sum"),
        wastage_cost=("Cost_Impact", "sum")).reset_index(), on="Item_ID", how="left")
    ratings = frame("ratings")
    scoped_orders = sales[["Order_ID", "Item_ID"]].drop_duplicates()
    ratings = ratings.merge(scoped_orders, on=["Order_ID", "Item_ID"], how="inner")
    rating_metrics = ratings.groupby("Item_ID").Stars.agg(["mean", "count"]).reset_index().rename(
        columns={"mean": "Average_Rating", "count": "Rating_Count"})
    grouped = grouped.merge(rating_metrics, on="Item_ID", how="left")
    grouped = include_unsold_menu_items(grouped.fillna({"wastage_quantity": 0, "wastage_cost": 0}))
    grouped = classify_items(grouped)
    grouped = add_slow_moving_evidence(grouped, sales, user, location_id)
    grouped = selected(grouped)
    grouped = grouped.sort_values("revenue", ascending=False)
    numeric = grouped.select_dtypes(include="number").columns
    grouped[numeric] = grouped[numeric].fillna(0)
    return {"total": len(grouped), "items": records(grouped.iloc[offset:offset + limit]),
            "method": "Multifactor descriptive classes and slow-moving evidence; rules, not supervised ML labels"}


@router.get("/analytics/slow-moving")
def slow_moving(location_id: int | None = None, category_id: int | None = None,
                status: str | None = None, limit: int = Query(150, ge=1, le=200),
                offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    items = pd.DataFrame(menu(location_id=location_id, category_id=category_id,
                              limit=200, offset=0, user=user)["items"])
    if status is not None:
        if status not in {"SLOW_MOVER", "WATCHLIST", "HIDDEN_OPPORTUNITY", "SEASONAL_REVIEW",
                          "INSUFFICIENT_HISTORY", "NO_OBSERVED_SALES", "NOT_SLOW"}:
            raise HTTPException(422, "Unknown slow-moving status")
        items = items[items.Slow_Moving_Status.eq(status)] if not items.empty else items
    columns = ["Item_ID", "Item_Name", "Category_ID", "Location_ID", "Scope", "Slow_Moving_Status",
               "Severity", "Evidence", "Reason", "History_Status", "Recommended_Action",
               "Slow_Moving_Rule_Version"]
    return {"total": len(items), "items": items.reindex(columns=columns).iloc[offset:offset + limit].to_dict("records"),
            "method": "Scoped multifactor rule using volume, order frequency, recency, trend, repeats, contribution, wastage, seasonality candidate, and history"}


@router.get("/analytics/menu/{item_id}")
def menu_item(item_id: int, location_id: int | None = None, user=Depends(auth.current_user)):
    rows = menu(location_id=location_id, limit=200, offset=0, user=user)["items"]
    result = next((row for row in rows if row["Item_ID"] == item_id), None)
    if result is None:
        raise HTTPException(404, "Item not found")
    return result


@router.get("/analytics/customers")
def customers(location_id: int | None = None, segment: str | None = None,
              limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    rfm = scoped_segments(user, location_id)
    if rfm.empty:
        return {"total": 0, "customers": [], "segment_counts": {}}
    counts = rfm.Segment.value_counts().to_dict()
    if segment:
        rfm = rfm[rfm.Segment.eq(segment)]
    rfm = rfm.sort_values("Monetary", ascending=False).rename(columns={
        "Last_Order": "last_order", "Frequency": "frequency", "Monetary": "monetary",
        "Recency_Days": "recency_days", "Segment": "segment", "Cluster": "cluster"})
    return {"total": len(rfm), "customers": records(rfm.iloc[offset:offset + limit]),
            "segment_counts": counts,
            "method": "Clean net-RFM scaled KMeans; labels derived from cluster profiles; rfm-kmeans-v4"}


@lru_cache(maxsize=1)
def customer_segment_artifact():
    path = MODELS / "customer_rfm_kmeans.joblib"
    if not path.is_file():
        raise HTTPException(503, "Clean customer segmentation model unavailable")
    try:
        return joblib.load(path)
    except (OSError, ValueError, EOFError) as exc:
        raise HTTPException(503, "Clean customer segmentation model unavailable") from exc


def scoped_segments(user, location_id=None):
    allowed = scope(user, location_id)
    if allowed is None:
        return frame("customer_segments")
    if len(allowed) == 1 and allowed[0] is None:
        return frame("customer_segments")
    sales = sales_for(user, location_id)
    if sales.empty:
        return pd.DataFrame(columns=["Customer_ID", "Last_Order", "Frequency", "Monetary", "Recency_Days", "Cluster", "Segment"])
    rfm = sales.groupby("Customer_ID").agg(Last_Order=("Order_DateTime", "max"),
        Frequency=("Order_ID", "nunique"), Monetary=("Net_Revenue", "sum")).reset_index()
    snapshot = frame("sales").Order_DateTime.max() + pd.Timedelta(days=1)
    rfm["Recency_Days"] = (snapshot - rfm.Last_Order).dt.days
    artifact = customer_segment_artifact()
    scaled = artifact["scaler"].transform(rfm_features(rfm)[artifact["features"]])
    rfm["Cluster"] = artifact["model"].predict(scaled)
    rfm["Segment"] = rfm.Cluster.map(artifact["labels"])
    return rfm


@router.get("/analytics/customers/profiles")
def customer_profiles(location_id: int | None = None, user=Depends(auth.current_user)):
    rfm = scoped_segments(user, location_id)
    if rfm.empty:
        return {"profiles": []}
    profiles = rfm.groupby(["Cluster", "Segment"], as_index=False).agg(
        size=("Customer_ID", "size"), average_recency=("Recency_Days", "mean"),
        average_frequency=("Frequency", "mean"), average_monetary=("Monetary", "mean"))
    return {"profiles": records(profiles), "version": customer_segment_artifact()["version"]}


@router.get("/analytics/customers/{customer_id}")
def customer(customer_id: int, location_id: int | None = None, user=Depends(auth.current_user)):
    sales = sales_for(user, location_id)
    own = sales[sales.Customer_ID.eq(customer_id)]
    if own.empty:
        raise HTTPException(404, "Customer not found in allowed scope")
    return {"customer_id": customer_id, "frequency": int(own.Order_ID.nunique()),
            "monetary": float(own.Net_Revenue.sum()), "last_order": own.Order_DateTime.max().isoformat()}


@router.get("/analytics/wastage")
def wastage(location_id: int | None = None, user=Depends(auth.current_user)):
    data = wastage_frame()
    allowed = scope(user, location_id)
    if allowed is not None:
        data = data[data.Location_ID.isin(allowed)]
    by_item = data.groupby("Item_ID", as_index=False).agg(quantity=("Quantity_Wasted", "sum"),
        cost=("Cost_Impact", "sum")).sort_values("cost", ascending=False)
    by_location = data.groupby("Location_ID", as_index=False).Cost_Impact.sum()
    return {"total_cost": float(data.Cost_Impact.sum()), "total_quantity": float(data.Quantity_Wasted.sum()),
            "high_wastage_items": records(by_item.head(20)), "locations": records(by_location),
            "prediction_status": "Separate prospective weekly model available; low recall on holdout, use as experimental"}


@router.get("/analytics/wastage/forecast")
def wastage_forecast(location_id: int | None = None, risk: str | None = None,
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     user=Depends(auth.current_user)):
    data = frame("wastage_next_week")
    allowed = scope(user, location_id)
    if allowed is not None:
        data = data[data.Location_ID.isin(allowed)]
    if risk:
        if risk not in {"LOW", "MEDIUM", "HIGH"}:
            raise HTTPException(422, "Unknown wastage risk band")
        data = data[data.Risk.eq(risk)]
    data = data.sort_values("Expected_Wastage", ascending=False)
    metrics_file = MODELS / "wastage_metrics.json"
    metrics = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.is_file() else {}
    return {"total": len(data), "predictions": records(data.iloc[offset:offset + limit]),
            "metrics": metrics, "is_estimate": True,
            "method": "Experimental next-week observed-record wastage estimate; absent source records remain unknown; prior-period features only"}


@router.get("/analytics/forecast")
def forecast(location_id: int | None = None, limit: int = Query(100, ge=1, le=600),
             offset: int = Query(0, ge=0), user=Depends(auth.current_user),
             grain: Literal["location", "item", "category"] | None = None,
             entity_id: int | None = Query(None, gt=0), horizon: int = Query(7, ge=1, le=30),
             mode: Literal["future", "backtest"] = "future"):
    if grain is not None:
        if horizon not in (1, 7, 14, 30):
            raise HTTPException(422, "Supported horizons are 1, 7, 14, and 30 days")
        if grain == "location":
            if entity_id is None:
                entity_id = location_id
            elif location_id is not None and entity_id != location_id:
                raise HTTPException(422, "Location and entity IDs disagree")
            if entity_id is None:
                raise HTTPException(422, "Location entity_id is required")
            scope(user, entity_id)
        else:
            if location_id is not None:
                raise HTTPException(422, "Item and category forecasts are global; omit location_id")
            if "REGIONAL_MANAGER" in user["roles"] and "ADMIN" not in user["roles"]:
                raise HTTPException(403, "Global item/category forecasts are not available to regional accounts")
            if entity_id is None:
                raise HTTPException(422, "entity_id is required")
        metrics_path = MODELS / "multigrain_metrics.json"
        artifact_path = MODELS / f"multigrain_{grain}.joblib"
        if not metrics_path.is_file() or not artifact_path.is_file():
            raise HTTPException(503, "Grain forecasts not generated")
        try:
            artifact = joblib.load(artifact_path)
        except (OSError, ValueError, EOFError) as exc:
            raise HTTPException(503, "Grain forecast model unavailable") from exc
        if entity_id not in artifact["last_history"]:
            raise HTTPException(404, "Forecast entity has no trained history")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))["grains"][grain]["test"][str(horizon)]
        if mode == "backtest":
            holdout = pd.read_parquet(MODELS / "multigrain_holdout.parquet")
            data = holdout[(holdout.Grain.eq(grain.upper())) &
                           (holdout.Entity_ID.eq(entity_id)) & (holdout.Lead.le(horizon))].copy()
            if data.empty:
                raise HTTPException(422, "Entity lacks seven pre-test days for recursive backtesting")
        else:
            start = pd.Timestamp(artifact["last_date"]) + pd.Timedelta(days=1)
            data = recursive_forecast(artifact["model"],
                                      {entity_id: artifact["last_history"][entity_id]}, start, horizon)
            data["Actual"] = None
        data = data.sort_values("Date")
        return {"grain": grain.upper(), "entity_id": entity_id, "horizon": horizon, "mode": mode,
                "model_version": artifact["version"], "dataset_version": artifact["dataset_version"],
                "status": "EXPERIMENTAL", "metrics": metrics, "total": len(data), "forecasts": records(data),
                "method": "Recursive forecast; later leads use prior predictions, never future actual demand"}
    path = MODELS / "dual_pipeline_comparison.csv"
    if not path.is_file():
        raise HTTPException(503, "Comparison not generated")
    data = pd.read_csv(path)
    allowed = scope(user, location_id)
    if allowed is not None:
        data = data[data.Location_ID.isin(allowed)]
    return {"total": len(data), "forecasts": records(data.iloc[offset:offset + limit])}


@router.get("/models/comparison")
def comparison(location_id: int | None = None, limit: int = Query(100, ge=1, le=600),
               offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    result = forecast(location_id, limit, offset, user)
    all_cases = pd.read_csv(MODELS / "dual_pipeline_comparison.csv")
    allowed = scope(user, location_id)
    if allowed is not None:
        all_cases = all_cases[all_cases.Location_ID.isin(allowed)]
    result["summary"] = {"case_count": len(all_cases),
        "spark_mae": float(all_cases.Spark_Error.mean()) if len(all_cases) else None,
        "python_mae": float(all_cases.Python_Error.mean()) if len(all_cases) else None,
        "average_difference": float(all_cases.Difference.mean()) if len(all_cases) else None,
        "agreement_percentage": float(100 * all_cases.Match_Status.eq("Match").mean()) if len(all_cases) else None,
        "tolerance_units": 50.0}
    return result


@router.get("/analytics/pricing")
def pricing(item_id: int | None = None, location_id: int | None = None,
            limit: int = Query(100, ge=1, le=200), user=Depends(auth.current_user)):
    sales = sales_for(user, location_id)
    with database.connection() as db:
        changes = [dict(row) for row in db.execute("SELECT item_id,price,effective_date FROM pricing_history ORDER BY item_id,effective_date")]
    changes = pd.DataFrame(changes)
    if item_id is not None:
        changes = changes[changes.item_id.eq(item_id)]
    observations = []
    changes["Previous_List_Price"] = changes.groupby("item_id").price.shift(1)
    changed = changes[changes.Previous_List_Price.notna() & changes.price.ne(changes.Previous_List_Price)]
    for row in changed.itertuples():
        date = local_day_start(row.effective_date)
        item_sales = sales[sales.Item_ID.eq(row.item_id)]
        before = item_sales[item_sales.Order_DateTime.ge(date - pd.Timedelta(days=30)) & item_sales.Order_DateTime.lt(date)]
        after = item_sales[item_sales.Order_DateTime.ge(date) & item_sales.Order_DateTime.lt(date + pd.Timedelta(days=30))]
        if before.empty or after.empty:
            continue
        previous_price = float((before.Quantity * before.Unit_Price).sum() / before.Quantity.sum())
        new_price = float((after.Quantity * after.Unit_Price).sum() / after.Quantity.sum())
        before_metrics, after_metrics = sales_metrics(before), sales_metrics(after)
        observed_price_change = 100 * (new_price / previous_price - 1)
        observations.append({"Item_ID": row.item_id, "Effective_Date": row.effective_date,
            "Previous_List_Price": float(row.Previous_List_Price), "New_List_Price": float(row.price),
            "List_Price_Change_Percent": 100 * (row.price / row.Previous_List_Price - 1),
            "Before_Quantity": before_metrics["quantity"], "After_Quantity": after_metrics["quantity"],
            "Before_Avg_Price": previous_price, "After_Avg_Price": new_price,
            "Observed_Price_Change_Percent": observed_price_change,
            "Demand_Change_Percent": 100 * (after_metrics["quantity"] / before_metrics["quantity"] - 1),
            "Revenue_Change_Percent": 100 * (after_metrics["net_revenue"] / max(before_metrics["net_revenue"], 1) - 1),
            "Contribution_Change_Percent": 100 * (after_metrics["contribution"] - before_metrics["contribution"]) /
                max(abs(before_metrics["contribution"]), 1),
            "Sensitivity": sensitivity(previous_price, new_price, before_metrics["quantity"], after_metrics["quantity"])})
        if len(observations) >= limit:
            break
    return {"total": len(observations), "historical_price_change_events": len(changed), "observations": observations,
            "method": "Equal 30-day windows around actual listed price changes; observed unit price is checked; association only"}


@router.get("/analytics/promotions")
def promotions(location_id: int | None = None, user=Depends(auth.current_user)):
    sales = sales_for(user, location_id)
    with database.connection() as db:
        campaigns = [dict(r) for r in db.execute("SELECT * FROM promotions ORDER BY promotion_id")]
    waste = wastage_frame()
    allowed = scope(user, location_id)
    if allowed is not None:
        waste = waste[waste.Location_ID.isin(allowed)]
    lower, upper = sales.Order_DateTime.min(), sales.Order_DateTime.max()
    outputs = []
    for campaign in campaigns:
        if campaign.get("location_id") is not None and allowed is not None and campaign["location_id"] not in allowed:
            continue
        eligible = get_eligible_sales_for_promotion(sales, campaign)
        start = local_day_start(campaign["start_date"])
        end = local_day_after(campaign["end_date"])
        span = end - start
        before_window = eligible[eligible.Order_DateTime.ge(start - span) & eligible.Order_DateTime.lt(start)]
        during_window = get_eligible_sales_for_promotion(sales, campaign, during=True)
        after_window = eligible[eligible.Order_DateTime.ge(end) & eligible.Order_DateTime.lt(end + span)]
        before = sales_metrics(before_window) if start - span >= lower else None
        during = sales_metrics(during_window)
        after = sales_metrics(after_window) if end + span <= upper else None
        tagged = during_window[during_window.Promotion_ID.eq(campaign["promotion_id"])]
        item_ids = eligible.Item_ID.unique()
        campaign_waste = waste[waste.Item_ID.isin(item_ids)]
        if campaign.get("location_id") is not None:
            campaign_waste = campaign_waste[campaign_waste.Location_ID.eq(campaign["location_id"])]
        during_waste = campaign_waste[campaign_waste.Wastage_Date.ge(start.tz_localize(None)) &
                                      campaign_waste.Wastage_Date.lt(end.tz_localize(None))]
        repeat = during_window.groupby("Customer_ID").Order_ID.nunique().gt(1).sum() if not during_window.empty else 0
        outputs.append({"Promotion_ID": campaign["promotion_id"], "promotion_name": campaign["promotion_name"],
            "discount_percent": campaign["discount_percent"], "start_date": campaign["start_date"],
            "end_date": campaign["end_date"], "quantity": during["quantity"],
            "revenue": during["net_revenue"], "contribution": during["contribution"],
            "orders": during["orders"], "customers": during["customers"], "aov": during["aov"],
            "tagged_campaign_orders": int(tagged.Order_ID.nunique()),
            "eligible_item_count": int(len(item_ids)),
            "repeat_customers": int(repeat), "wastage_cost": float(during_waste.Cost_Impact.sum()),
            "before": before, "during": during, "after": after,
            "promotion_trap": promotion_trap(before, during) if before else None,
            "comparison_available": before is not None})
    return {"campaigns": outputs,
            "method": "Asia/Karachi equal before/during/after windows for item, category, or global target intersected with location; trap is sales-up/contribution-down; observational only"}


@router.get("/analytics/anomalies")
def anomalies(location_id: int | None = None, user=Depends(auth.current_user)):
    sales = sales_for(user, location_id)
    daily = sales.groupby(["Date", "Location_ID"], as_index=False).agg(quantity=("Quantity", "sum"),
        revenue=("Net_Revenue", "sum"))
    if daily.empty:
        return {"sales": [], "unusual_orders": []}
    grouped = daily.groupby("Location_ID").quantity
    daily["z_score"] = (daily.quantity - grouped.transform("mean")) / grouped.transform("std").replace(0, 1)
    spikes = daily[daily.z_score.abs().gt(3)].sort_values("z_score", key=lambda s: s.abs(), ascending=False)
    orders = sales.groupby("Order_ID", as_index=False).agg(revenue=("Net_Revenue", "sum"),
        discount=("Discount_Applied", "sum"), quantity=("Quantity", "sum"))
    discount_rate = orders.discount / (orders.revenue + orders.discount).where((orders.revenue + orders.discount).ne(0))
    unusual = orders[discount_rate.gt(.5) | orders.quantity.gt(orders.quantity.quantile(.999))]
    ratings = frame("ratings")
    eligible = sales[["Order_ID", "Item_ID"]].drop_duplicates()
    ratings = ratings.merge(eligible, on=["Order_ID", "Item_ID"], how="inner")
    ratings["Rating_Day"] = local_dates(parse_order_timestamps(ratings.Rating_Date)).astype(str)
    daily_ratings = ratings.groupby(["Item_ID", "Rating_Day"], as_index=False).agg(
        count=("Stars", "size"), average_stars=("Stars", "mean"), five_star_rate=("Stars", lambda x: x.eq(5).mean()))
    baseline = daily_ratings.groupby("Item_ID").agg(item_daily_mean=("count", "mean"),
        item_daily_std=("count", "std")).reset_index()
    daily_ratings = daily_ratings.merge(baseline, on="Item_ID")
    daily_ratings["count_z_score"] = ((daily_ratings["count"] - daily_ratings.item_daily_mean) /
        daily_ratings.item_daily_std.fillna(1).replace(0, 1))
    rating_flags = daily_ratings[daily_ratings["count"].ge(5) & daily_ratings.count_z_score.gt(3)]
    return {"sales": records(spikes.head(100)), "unusual_orders": records(unusual.head(100)),
            "ratings": records(rating_flags.sort_values("count_z_score", ascending=False).head(100)),
            "method": "Sales location-day |z|>3; rating item-day count z>3 and >=5 valid ratings; unusual order rules"}


@router.get("/analytics/channels")
def channels(location_id: int | None = None, user=Depends(auth.current_user)):
    sales = sales_for(user, location_id)
    grouped = sales.groupby("Channel", as_index=False).agg(
        quantity=("Quantity", "sum"), revenue=("Net_Revenue", "sum"),
        contribution=("Contribution", "sum"), orders=("Order_ID", "nunique"),
        customers=("Customer_ID", "nunique"))
    grouped["aov"] = grouped.revenue / grouped.orders.where(grouped.orders.ne(0))
    return {"channels": records(grouped.fillna(0)),
            "method": "Completed clean sales grouped by ordering channel"}


@router.get("/analytics/locations")
def location_comparison(user=Depends(auth.current_user)):
    sales = sales_for(user)
    grouped = sales.groupby("Location_ID", as_index=False).agg(
        revenue=("Net_Revenue", "sum"), contribution=("Contribution", "sum"),
        orders=("Order_ID", "nunique"), customers=("Customer_ID", "nunique"))
    grouped["aov"] = grouped.revenue / grouped.orders.where(grouped.orders.ne(0))
    grouped["profit_percent"] = 100 * grouped.contribution / grouped.revenue.where(grouped.revenue.ne(0))
    waste = wastage_frame().groupby("Location_ID", as_index=False).Cost_Impact.sum().rename(
        columns={"Cost_Impact": "wastage_cost"})
    grouped = grouped.merge(waste, on="Location_ID", how="left").fillna(0)
    grouped["revenue_rank"] = grouped.revenue.rank(ascending=False, method="min").astype(int)
    return {"locations": records(grouped.sort_values("revenue_rank")),
            "method": "Same clean completed-sales indicators across assigned locations"}


@router.get("/analytics/churn")
def churn(location_id: int | None = None, limit: int = Query(100, ge=1, le=500),
          user=Depends(auth.current_user)):
    sales = sales_for(user, location_id)
    if sales.empty:
        return {"at_risk": [], "total": 0}
    end = frame("sales").Order_DateTime.max()
    recent = sales[sales.Order_DateTime.gt(end - pd.Timedelta(days=90))].groupby("Customer_ID").Order_ID.nunique()
    previous = sales[sales.Order_DateTime.le(end - pd.Timedelta(days=90)) &
                     sales.Order_DateTime.gt(end - pd.Timedelta(days=180))].groupby("Customer_ID").Order_ID.nunique()
    rfm = scoped_segments(user, location_id).copy()
    rfm["recent_orders"] = rfm.Customer_ID.map(recent).fillna(0).astype(int)
    rfm["previous_orders"] = rfm.Customer_ID.map(previous).fillna(0).astype(int)
    rfm["declining"] = rfm.previous_orders.ge(2) & rfm.recent_orders.lt(rfm.previous_orders * .5)
    rfm["at_risk"] = rfm.Recency_Days.gt(90) | rfm.declining
    at_risk = rfm[rfm.at_risk].sort_values(["Recency_Days", "Monetary"], ascending=[False, False])
    return {"total": len(at_risk), "at_risk": records(at_risk.head(limit)),
            "method": "Recency >90 days or recent 90-day orders < half prior 90-day orders after at least two prior orders"}


@router.get("/analytics/recommendations")
def recommendations(location_id: int | None = None, user=Depends(auth.current_user)):
    items = menu(location_id=location_id, limit=200, offset=0, user=user)["items"]
    proposed = []
    timestamp = pd.Timestamp.now(tz="UTC").isoformat()
    def add(kind, entity, action, priority, evidence, reason):
        proposed.append({"id": f"{kind}:{entity}:{location_id or 'all'}", "type": kind,
            "entity_id": entity, "action": action, "priority": priority, "evidence": evidence,
            "reason": reason, "rule_version": "evidence-rules-v2",
            "dataset_version": "phase1-v1-clean-v3", "generated_at": timestamp})
    for item in items:
        if item["Slow_Moving_Status"] in {"SLOW_MOVER", "WATCHLIST", "HIDDEN_OPPORTUNITY", "SEASONAL_REVIEW"}:
            priority = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low", "REVIEW": "Low"}[item["Severity"]]
            add("slow_moving", item["Item_ID"], item["Recommended_Action"], priority,
                item["Evidence"], item["Reason"])
        evidence = {"sales": item["sales"], "revenue": item["revenue"],
                    "contribution": item["contribution"], "rating": item["Average_Rating"],
                    "wastage_quantity": item["wastage_quantity"],
                    "promotion_dependency": item["promotion_dependency"]}
        if (item["classification"] == "Hidden Opportunity" and item["Average_Rating"] >= 4
                and item["Slow_Moving_Status"] != "HIDDEN_OPPORTUNITY"):
            action, priority, kind = "Increase visibility for this profitable, well-rated item", "High", "menu"
        elif item["classification"] == "Volume Driver" and item["contribution"] < 0:
            action, priority, kind = "Review price or cost; high volume has negative contribution", "Critical", "pricing"
        elif item["wastage_quantity"] > item["sales"] * .2 and item["wastage_quantity"] > 100:
            action, priority, kind = "Review preparation quantity and wastage", "High", "wastage"
        else:
            continue
        add(kind, item["Item_ID"], action, priority, evidence, item["classification"])
    waste = frame("wastage_next_week")
    allowed = scope(user, location_id)
    if allowed is not None:
        waste = waste[waste.Location_ID.isin(allowed)]
    with database.connection() as db:
        inventory = pd.DataFrame([dict(row) for row in db.execute(
            "SELECT item_id,location_id,stock_quantity,reorder_level FROM inventory_records")])
    if not inventory.empty:
        risk = waste[waste.Risk.eq("HIGH")].merge(inventory, left_on=["Item_ID", "Location_ID"],
                                                   right_on=["item_id", "location_id"], how="left")
        for row in risk.itertuples():
            add("inventory", f"{row.Item_ID}:{row.Location_ID}",
                "Review next-week preparation and stock against forecast wastage", "High",
                {"expected_wastage": float(row.Expected_Wastage), "risk": row.Risk,
                 "stock_quantity": None if pd.isna(row.stock_quantity) else float(row.stock_quantity),
                 "reorder_level": None if pd.isna(row.reorder_level) else float(row.reorder_level)},
                "Prospective high wastage risk; model recall is limited")
    profiles = customer_profiles(location_id=location_id, user=user)["profiles"]
    for profile in profiles:
        if profile["Segment"] == "At Risk" and profile["size"] > 0:
            add("customer_targeting", profile["Cluster"],
                "Review re-engagement offer for this at-risk segment", "Medium",
                {"segment_size": profile["size"], "average_recency": profile["average_recency"],
                 "average_monetary": profile["average_monetary"]}, "Profiled clean-RFM cluster")
    if "REGIONAL_MANAGER" not in user["roles"] or "ADMIN" in user["roles"]:
        rules_path = DATA / "basket_rules.csv"
        if rules_path.is_file():
            rules = pd.read_csv(rules_path).head(10)
            for row in rules.itertuples():
                add("bundle", f"{row.Antecedent_Item_ID}:{row.Consequent_Item_ID}",
                    "Consider cross-selling this observed item pair", "Medium",
                    {"support": float(row.Support), "confidence": float(row.Confidence),
                     "lift": float(row.Lift), "pair_count": int(row.Pair_Count)},
                    "Observed basket association; no causal benefit assumed")
    for campaign in promotions(location_id=location_id, user=user)["campaigns"]:
        if campaign["promotion_trap"] is True:
            add("promotion", campaign["Promotion_ID"],
                "Review campaign: units rose while contribution fell", "Critical",
                {"before": campaign["before"], "during": campaign["during"]},
                "Equal-window observational promotion trap")
    if "REGIONAL_MANAGER" not in user["roles"] or "ADMIN" in user["roles"]:
        with database.connection() as db:
            for rec in proposed:
                db.execute("""INSERT INTO recommendations(recommendation_type,entity_id,action,priority,
                    evidence_json,reason,rule_version,generated_at,dataset_version,rec_key,location_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(rec_key) DO UPDATE SET action=excluded.action,
                    priority=excluded.priority,evidence_json=excluded.evidence_json,reason=excluded.reason,
                    generated_at=excluded.generated_at""",
                    (rec["type"], str(rec["entity_id"]), rec["action"], rec["priority"],
                     json.dumps(rec["evidence"]), rec["reason"], rec["rule_version"],
                     rec["generated_at"], rec["dataset_version"], rec["id"], location_id))
    return {"total": len(proposed), "recommendations": proposed,
            "method": "Deterministic evidence rules on clean metrics, cluster profiles, wastage forecast, baskets and campaign windows"}


@router.get("/analytics/basket")
def basket_rules(limit: int = Query(50, ge=1, le=200), user=Depends(auth.current_user)):
    if "REGIONAL_MANAGER" in user["roles"] and "ADMIN" not in user["roles"]:
        raise HTTPException(403, "Global basket rules are not available to regional accounts")
    path = DATA / "basket_rules.csv"
    if not path.is_file():
        raise HTTPException(503, "Basket rules not generated")
    rules = pd.read_csv(path)
    return {"total": len(rules), "rules": records(rules.head(limit)),
            "method": "Clean completed baskets, pair count >=100, lift >=1.05; observational association"}


@lru_cache(maxsize=1)
def python_forecast_artifact():
    path = MODELS / "python_forecast.joblib"
    if not path.is_file():
        raise HTTPException(503, "Python forecast model unavailable")
    try:
        return joblib.load(path)
    except (OSError, ValueError, EOFError) as exc:
        raise HTTPException(503, "Python forecast model unavailable") from exc


@router.post("/models/forecast/predict")
def predict_next_day(location_id: int, user=Depends(auth.current_user)):
    scope(user, location_id)
    daily = frame("location_daily")
    history = daily[daily.Location_ID.eq(location_id)].sort_values("Date")
    if len(history) < 7:
        raise HTTPException(422, "At least seven observed days are required")
    next_date = pd.Timestamp(history.Date.iloc[-1]) + pd.Timedelta(days=1)
    values = {"Location_ID": location_id, "day_of_week": next_date.dayofweek,
              "month": next_date.month, "lag_1": float(history.Demand.iloc[-1]),
              "lag_7": float(history.Demand.iloc[-7]),
              "rolling_7": float(history.Demand.iloc[-7:].mean())}
    artifact = python_forecast_artifact()
    estimate = max(0.0, float(artifact["model"].predict(pd.DataFrame([values])[artifact["features"]])[0]))
    case_id = f"{next_date.date()}:{location_id}"
    with database.connection() as db:
        db.execute("""INSERT INTO predictions(case_id,actual,prediction,model_name,model_version,dataset_version,created_at)
            VALUES(?,NULL,?,'python_location_forecast',?,?,datetime('now'))""",
            (case_id, estimate, artifact["version"], artifact["dataset_version"]))
    database.audit("forecast_prediction", user["id"], "location", location_id,
                   {"case_id": case_id, "model_version": artifact["version"]})
    return {"case_id": case_id, "location_id": location_id, "forecast_date": str(next_date.date()),
            "prediction": estimate, "model_name": "python_location_forecast",
            "model_version": artifact["version"], "dataset_version": artifact["dataset_version"],
            "is_estimate": True, "features": values, "actual": None}


class Scenario(BaseModel):
    item_id: int
    location_id: int | None = None
    promotion_id: int | None = None
    price_change_percent: float = Field(0, ge=-90, le=200)
    discount_change_percent: float = Field(0, ge=-100, le=100)
    demand_change_percent: float = Field(0, ge=-90, le=200)
    preparation_change_percent: float = Field(0, ge=-90, le=200)
    promotion_discount_percent: float | None = Field(None, ge=0, le=90)


@router.post("/what-if")
def what_if(payload: Scenario, user=Depends(auth.require_roles("ADMIN", "MANAGER", "REGIONAL_MANAGER", "ANALYST"))):
    sales = sales_for(user, payload.location_id)
    own = sales[sales.Item_ID.eq(payload.item_id)]
    if payload.promotion_id is not None:
        with database.connection() as db:
            row = db.execute("SELECT * FROM promotions WHERE promotion_id=?", (payload.promotion_id,)).fetchone()
        if row is None:
            raise HTTPException(422, "Unknown promotion")
        own = get_eligible_sales_for_promotion(own, dict(row), during=True)
    if own.empty:
        raise HTTPException(404, "Item has no eligible sales in allowed scope")
    quantity = float(own.Quantity.sum())
    revenue = float(own.Net_Revenue.sum())
    cost_per_unit = float(own.Cost_Total.sum()) / quantity
    price = float((own.Quantity * own.Unit_Price).sum()) / quantity
    discount = float(own.Discount_Applied.sum()) / quantity
    scenario_quantity = quantity * (1 + payload.demand_change_percent / 100)
    scenario_price = price * (1 + payload.price_change_percent / 100)
    scenario_discount = max(0, discount * (1 + payload.discount_change_percent / 100))
    if payload.promotion_discount_percent is not None:
        scenario_discount = scenario_price * payload.promotion_discount_percent / 100
    scenario_revenue = scenario_quantity * max(0, scenario_price - scenario_discount)
    baseline = {"quantity": quantity, "revenue": revenue, "contribution": float(own.Contribution.sum())}
    proposed = {"quantity": scenario_quantity, "revenue": scenario_revenue,
                "contribution": scenario_revenue - scenario_quantity * cost_per_unit}
    waste = wastage_frame()
    allowed = scope(user, payload.location_id)
    if allowed is not None:
        waste = waste[waste.Location_ID.isin(allowed)]
    waste = waste[waste.Item_ID.eq(payload.item_id)]
    if not waste.empty:
        baseline_waste = float(waste.Quantity_Wasted.sum())
        baseline_prepared = float(waste.Prepared_Quantity.sum())
        scenario_prepared = baseline_prepared * (1 + payload.preparation_change_percent / 100)
        scenario_waste = max(0, baseline_waste + (scenario_prepared - baseline_prepared) -
                             (scenario_quantity - quantity))
        baseline.update(wastage_units=baseline_waste, wastage_cost=baseline_waste * cost_per_unit)
        proposed.update(wastage_units=scenario_waste, wastage_cost=scenario_waste * cost_per_unit)
    database.audit("what_if", user["id"], "item", payload.item_id, payload.model_dump())
    return {"is_estimate": True, "baseline": baseline, "scenario": proposed,
            "delta": {key: proposed[key] - baseline[key] for key in baseline},
            "assumptions": {**payload.model_dump(), "demand_response_to_price": "user supplied; no causal elasticity inferred",
                            "preparation_effect": "historical prepared/wasted totals adjusted by assumed preparation and demand changes; simplified estimate" if not waste.empty else "unavailable without wastage history"}}
