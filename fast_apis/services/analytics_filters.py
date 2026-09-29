"""Typed filter contract shared by analytical screens and exports."""

from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator


MAX_ID = 9_223_372_036_854_775_807
Channel = Literal["Dine-in", "Takeaway", "Website", "App", "Third-Party Delivery"]


class AnalyticsFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    location_id: int | None = Field(default=None, gt=0, le=MAX_ID)
    item_id: int | None = Field(default=None, gt=0, le=MAX_ID)
    category_id: int | None = Field(default=None, gt=0, le=MAX_ID)
    channel: Channel | None = None
    promotion_id: int | None = Field(default=None, gt=0, le=MAX_ID)
    segment: str | None = None
    performance_class: Literal["Profit Driver", "Volume Driver", "Hidden Opportunity", "Low Performer"] | None = None
    slow_status: Literal["SLOW_MOVER", "WATCHLIST", "HIDDEN_OPPORTUNITY", "SEASONAL_REVIEW", "INSUFFICIENT_HISTORY", "NO_OBSERVED_SALES", "NOT_SLOW"] | None = None
    rating: float | None = Field(default=None, ge=1, le=5)
    wastage_risk: Literal["LOW", "MEDIUM", "HIGH"] | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


SUPPORTED = {
    "dashboard": {"date_from", "date_to", "location_id", "item_id", "category_id", "channel", "promotion_id"},
    "menu": {"date_from", "date_to", "location_id", "item_id", "category_id", "channel",
             "promotion_id", "performance_class", "rating", "slow_status"},
    "slow-moving": {"location_id", "category_id"},
    "customers": {"location_id", "segment"},
    "forecast": {"location_id"},
    "wastage": {"location_id"},
    "promotions": {"location_id"},
    "basket": set(),
}


def checked_filters(resource, **values):
    unsupported = [key for key, value in values.items() if value is not None and key not in SUPPORTED[resource]]
    if unsupported:
        raise HTTPException(422, f"Unsupported {resource} filter: {', '.join(sorted(unsupported))}")
    try:
        return AnalyticsFilters.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(str(error["msg"]) for error in exc.errors())) from None
