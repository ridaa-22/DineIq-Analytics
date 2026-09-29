"""One population rule for historical and managed campaigns."""

import pandas as pd

from Python_Pipeline.business_time import local_day_after, local_day_start


def _value(campaign, *names):
    for name in names:
        if name in campaign and pd.notna(campaign[name]):
            return int(campaign[name])
    return None


def get_eligible_sales_for_promotion(sales, campaign, *, during=False):
    """Item target wins over category; null targets mean global; location intersects."""
    item = _value(campaign, "applicable_item_id", "Applicable_Item_ID")
    category = _value(campaign, "applicable_category_id", "Applicable_Category_ID")
    location = _value(campaign, "location_id", "Location_ID")
    if item is not None:
        selected = sales[sales.Item_ID.eq(item)]
    elif category is not None:
        selected = sales[sales.Category_ID.eq(category)]
    else:
        selected = sales
    if location is not None:
        selected = selected[selected.Location_ID.eq(location)]
    if during:
        start = local_day_start(campaign.get("start_date", campaign.get("Start_Date")))
        end = local_day_after(campaign.get("end_date", campaign.get("End_Date")))
        selected = selected[selected.Order_DateTime.ge(start) & selected.Order_DateTime.lt(end)]
    return selected
