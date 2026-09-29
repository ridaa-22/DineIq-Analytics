"""Allow-listed, location-scoped exports from current cleaned analytics."""

from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from fast_apis import database
from fast_apis.routes import dynamic
from fast_apis.services import auth_service as auth

router = APIRouter(prefix="/api")
ALLOWED = {"menu", "slow-moving", "customers", "forecast", "basket", "wastage", "promotions"}


@router.get("/exports/{report_name}")
def export(report_name: str, format: str = "csv", location_id: int | None = None,
           user=Depends(auth.current_user)):
    if report_name not in ALLOWED or format not in {"csv", "xlsx"}:
        raise HTTPException(404, "Export unavailable")
    if report_name == "menu":
        data = dynamic.menu(location_id=location_id, limit=200, offset=0, user=user)["items"]
    elif report_name == "slow-moving":
        data = dynamic.slow_moving(location_id=location_id, limit=200, offset=0, user=user)["items"]
    elif report_name == "customers":
        data = dynamic.customers(location_id=location_id, limit=100000, offset=0, user=user)["customers"]
    elif report_name == "forecast":
        data = dynamic.forecast(location_id=location_id, limit=600, offset=0, user=user)["forecasts"]
    elif report_name == "basket":
        data = dynamic.basket_rules(limit=200, user=user)["rules"]
    elif report_name == "wastage":
        data = dynamic.wastage(location_id=location_id, user=user)["high_wastage_items"]
    else:
        data = dynamic.promotions(location_id=location_id, user=user)["campaigns"]
    table = pd.DataFrame(data)
    for column in table.select_dtypes(include=["object", "string"]):
        table[column] = table[column].map(lambda value: "'" + value if isinstance(value, str)
            and value.startswith(("=", "+", "-", "@")) else value)
    buffer = BytesIO()
    if format == "csv":
        table.to_csv(buffer, index=False)
        media = "text/csv"
    else:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            table.to_excel(writer, index=False, sheet_name="DineIQ")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    buffer.seek(0)
    with database.connection() as db:
        db.execute("INSERT INTO exports(user_id,report_name,format,created_at,row_count) VALUES(?,?,?,?,?)",
                   (user["id"], report_name, format, __import__("time").time().__int__(), len(table)))
    database.audit("report_export", user["id"], "report", report_name,
                   {"format": format, "location_id": location_id, "row_count": len(table)})
    return StreamingResponse(buffer, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="dineiq-{report_name}.{format}"'})
