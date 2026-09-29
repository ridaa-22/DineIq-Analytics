"""Restaurant calendar boundaries for the Asia/Karachi data contract."""

import pandas as pd


BUSINESS_TZ = "Asia/Karachi"


def local_timestamp(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_localize(BUSINESS_TZ) if stamp.tzinfo is None else stamp.tz_convert(BUSINESS_TZ)


def local_day_start(value):
    return local_timestamp(value).normalize()


def local_day_after(value):
    return local_day_start(value) + pd.DateOffset(days=1)


def local_dates(values):
    if values.dt.tz is None:
        return values.dt.tz_localize(BUSINESS_TZ).dt.date
    return values.dt.tz_convert(BUSINESS_TZ).dt.date


def parse_order_timestamps(values):
    """Parse offset-aware source timestamps onto the restaurant clock."""
    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_convert(BUSINESS_TZ)
