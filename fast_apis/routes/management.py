"""Server-side role enforcement for application metadata and operational records."""

import json
import time
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict, model_validator

from fast_apis import database
from fast_apis.services import auth_service as auth
from fast_apis.services import job_service

router = APIRouter(prefix="/api")
admin = auth.require_roles("ADMIN")
business = auth.require_roles("ADMIN", "MANAGER")


def rows(cursor):
    return [dict(row) for row in cursor]


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str
    password: str = Field(min_length=8)
    role: str = "ANALYST"
    location_ids: list[int] = []


@router.post("/auth/register")
def public_register(payload: UserCreate):
    if payload.role != "ANALYST" or payload.location_ids:
        raise HTTPException(403, "Public registration creates Analyst accounts only")
    result, error = auth.register(payload.username, payload.email, payload.password)
    if error:
        raise HTTPException(409, error)
    return {"user": result}


@router.post("/auth/login")
def public_login(payload: dict):
    result = auth.login(str(payload.get("email", "")), str(payload.get("password", "")))
    if result is None:
        raise HTTPException(401, "Invalid email or password")
    return result


@router.post("/auth/logout")
def logout(credentials=Depends(auth.bearer), user=Depends(auth.current_user)):
    auth.logout(credentials.credentials, user)
    return {"success": True}


@router.get("/users")
def users(user=Depends(admin)):
    with database.connection() as db:
        return rows(db.execute("""SELECT u.id,u.username,u.email,u.is_active,
            GROUP_CONCAT(ur.role_name) roles FROM users u LEFT JOIN user_roles ur ON ur.user_id=u.id
            GROUP BY u.id ORDER BY u.id"""))


@router.post("/users")
def create_user(payload: UserCreate, user=Depends(admin)):
    result, error = auth.register(payload.username, payload.email, payload.password,
                                  payload.role, payload.location_ids)
    if error:
        raise HTTPException(409, error)
    database.audit("admin_create_user", user["id"], "user", result["id"], {"role": payload.role})
    return result


class RoleChange(BaseModel):
    role: str
    location_ids: list[int] = []
    is_active: bool = True


@router.put("/users/{user_id}/role")
def change_role(user_id: int, payload: RoleChange, user=Depends(admin)):
    if payload.role not in database.ROLES:
        raise HTTPException(422, "Invalid role")
    with database.connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(404, "User not found")
        db.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
        db.execute("INSERT INTO user_roles(user_id,role_name) VALUES(?,?)", (user_id, payload.role))
        db.execute("DELETE FROM user_locations WHERE user_id=?", (user_id,))
        for location_id in payload.location_ids:
            if not db.execute("SELECT 1 FROM restaurant_locations WHERE location_id=?", (location_id,)).fetchone():
                raise HTTPException(422, "Unknown location")
            db.execute("INSERT INTO user_locations(user_id,location_id) VALUES(?,?)", (user_id, location_id))
        db.execute("UPDATE users SET is_active=? WHERE id=?", (int(payload.is_active), user_id))
    database.audit("role_changed", user["id"], "user", user_id, payload.model_dump())
    return {"success": True}


@router.get("/locations")
def locations(user=Depends(auth.current_user)):
    with database.connection() as db:
        result = rows(db.execute("SELECT * FROM restaurant_locations ORDER BY location_id"))
    allowed = auth.allowed_location(user)
    return [r for r in result if r["location_id"] in allowed] if isinstance(allowed, list) else result


class LocationUpdate(BaseModel):
    location_name: str
    city: str = ""
    address: str = ""
    is_active: bool = True


@router.post("/locations")
def add_location(payload: LocationUpdate, user=Depends(admin)):
    with database.connection() as db:
        cursor = db.execute("INSERT INTO restaurant_locations(location_name,city,address,is_active) VALUES(?,?,?,?)",
                            (payload.location_name, payload.city, payload.address, int(payload.is_active)))
        identity = cursor.lastrowid
    database.audit("location_created", user["id"], "location", identity, payload.model_dump())
    return {"location_id": identity}


@router.put("/locations/{location_id}")
def edit_location(location_id: int, payload: LocationUpdate, user=Depends(admin)):
    with database.connection() as db:
        cursor = db.execute("UPDATE restaurant_locations SET location_name=?,city=?,address=?,is_active=? WHERE location_id=?",
                            (payload.location_name, payload.city, payload.address, int(payload.is_active), location_id))
        if not cursor.rowcount:
            raise HTTPException(404, "Location not found")
    database.audit("location_updated", user["id"], "location", location_id, payload.model_dump())
    return {"success": True}


@router.get("/menu/items")
def metadata_items(user=Depends(auth.current_user)):
    with database.connection() as db:
        return rows(db.execute("SELECT * FROM menu_items ORDER BY item_id"))


class ItemUpdate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    item_name: str
    category_id: int
    base_price: float = Field(gt=0, le=1_000_000)
    cost: float = Field(ge=0, le=1_000_000)
    description: str = ""
    is_available: bool = True


@router.get("/menu/categories")
def categories(user=Depends(auth.current_user)):
    with database.connection() as db:
        return rows(db.execute("SELECT * FROM menu_categories ORDER BY category_id"))


class CategoryCreate(BaseModel):
    category_name: str = Field(min_length=2, max_length=100)


@router.post("/menu/categories")
def add_category(payload: CategoryCreate, user=Depends(business)):
    with database.connection() as db:
        identity = db.execute("INSERT INTO menu_categories(category_name) VALUES(?)",
                              (payload.category_name,)).lastrowid
    database.audit("category_created", user["id"], "category", identity, payload.model_dump())
    return {"category_id": identity}


@router.put("/menu/categories/{category_id}")
def edit_category(category_id: int, payload: CategoryCreate, user=Depends(business)):
    with database.connection() as db:
        changed = db.execute("UPDATE menu_categories SET category_name=? WHERE category_id=?",
                             (payload.category_name, category_id)).rowcount
        if not changed:
            raise HTTPException(404, "Category not found")
    database.audit("category_updated", user["id"], "category", category_id, payload.model_dump())
    return {"success": True}


@router.post("/menu/items")
def add_item(payload: ItemUpdate, user=Depends(business)):
    with database.connection() as db:
        if not db.execute("SELECT 1 FROM menu_categories WHERE category_id=?", (payload.category_id,)).fetchone():
            raise HTTPException(422, "Unknown category")
        identity = db.execute("""INSERT INTO menu_items(item_name,category_id,base_price,cost,description,is_available)
            VALUES(?,?,?,?,?,?)""", (payload.item_name, payload.category_id, payload.base_price,
                                       payload.cost, payload.description, int(payload.is_available))).lastrowid
        db.execute("INSERT INTO pricing_history(item_id,price,effective_date,changed_by) VALUES(?,?,date('now'),?)",
                   (identity, payload.base_price, user["id"]))
    database.audit("menu_item_created", user["id"], "item", identity, payload.model_dump())
    return {"item_id": identity, "historical_data_recomputed": False}


@router.put("/menu/items/{item_id}")
def edit_item(item_id: int, payload: ItemUpdate, user=Depends(business)):
    with database.connection() as db:
        if not db.execute("SELECT 1 FROM menu_categories WHERE category_id=?", (payload.category_id,)).fetchone():
            raise HTTPException(422, "Unknown category")
        old = db.execute("SELECT base_price FROM menu_items WHERE item_id=?", (item_id,)).fetchone()
        if old is None:
            raise HTTPException(404, "Item not found")
        db.execute("""UPDATE menu_items SET item_name=?,category_id=?,base_price=?,cost=?,description=?,is_available=?
            WHERE item_id=?""", (payload.item_name, payload.category_id, payload.base_price, payload.cost,
                                 payload.description, int(payload.is_available), item_id))
        if old[0] != payload.base_price:
            db.execute("INSERT INTO pricing_history(item_id,price,effective_date,changed_by) VALUES(?,?,date('now'),?)",
                       (item_id, payload.base_price, user["id"]))
    database.audit("menu_item_updated", user["id"], "item", item_id, payload.model_dump())
    return {"success": True, "historical_data_recomputed": False}


@router.get("/pricing/history")
def price_history(item_id: int | None = None, user=Depends(auth.current_user)):
    with database.connection() as db:
        if item_id is None:
            return rows(db.execute("SELECT * FROM pricing_history ORDER BY effective_date DESC,pricing_id DESC LIMIT 500"))
        return rows(db.execute("SELECT * FROM pricing_history WHERE item_id=? ORDER BY effective_date DESC,pricing_id DESC",
                               (item_id,)))


@router.get("/promotions")
def promotions(user=Depends(auth.current_user)):
    with database.connection() as db:
        return rows(db.execute("SELECT * FROM promotions ORDER BY promotion_id"))


class PromotionUpdate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    promotion_name: str
    discount_percent: float = Field(ge=0, le=100)
    start_date: date
    end_date: date
    applicable_item_id: int | None = None
    applicable_category_id: int | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.start_date > self.end_date:
            raise ValueError("Promotion end date precedes start date")
        return self


def validate_promotion_refs(db, payload):
    for table, column, value in (("menu_items", "item_id", payload.applicable_item_id),
                                 ("menu_categories", "category_id", payload.applicable_category_id)):
        if value is not None and not db.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (value,)).fetchone():
            raise HTTPException(422, f"Unknown {column}")


@router.post("/promotions")
def add_promotion(payload: PromotionUpdate, user=Depends(business)):
    with database.connection() as db:
        validate_promotion_refs(db, payload)
        identity = db.execute("""INSERT INTO promotions(promotion_name,discount_percent,start_date,end_date,
            applicable_item_id,applicable_category_id) VALUES(?,?,?,?,?,?)""",
            (payload.promotion_name, payload.discount_percent, payload.start_date.isoformat(), payload.end_date.isoformat(),
             payload.applicable_item_id, payload.applicable_category_id)).lastrowid
    database.audit("promotion_created", user["id"], "promotion", identity, payload.model_dump(mode="json"))
    return {"promotion_id": identity}


@router.put("/promotions/{promotion_id}")
def edit_promotion(promotion_id: int, payload: PromotionUpdate, user=Depends(business)):
    with database.connection() as db:
        validate_promotion_refs(db, payload)
        cursor = db.execute("""UPDATE promotions SET promotion_name=?,discount_percent=?,start_date=?,end_date=?,
            applicable_item_id=?,applicable_category_id=? WHERE promotion_id=?""",
            (payload.promotion_name, payload.discount_percent, payload.start_date.isoformat(), payload.end_date.isoformat(),
             payload.applicable_item_id, payload.applicable_category_id, promotion_id))
        if not cursor.rowcount:
            raise HTTPException(404, "Promotion not found")
    database.audit("promotion_updated", user["id"], "promotion", promotion_id, payload.model_dump(mode="json"))
    return {"success": True}


@router.get("/inventory")
def inventory(location_id: int | None = None, limit: int = Query(100, ge=1, le=500),
              offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    allowed = auth.allowed_location(user, location_id)
    with database.connection() as db:
        if isinstance(allowed, list):
            marks = ",".join("?" for _ in allowed)
            condition, params = f"WHERE location_id IN ({marks})", tuple(allowed)
        elif allowed is not None:
            condition, params = "WHERE location_id=?", (allowed,)
        else:
            condition, params = "", ()
        total = db.execute(f"SELECT COUNT(*) FROM inventory_records {condition}", params).fetchone()[0]
        result = rows(db.execute(f"SELECT * FROM inventory_records {condition} ORDER BY inventory_id LIMIT ? OFFSET ?",
                                 (*params, limit, offset)))
    return {"total": total, "records": result}


class InventoryUpdate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    location_id: int
    item_id: int
    stock_quantity: float = Field(ge=0, multiple_of=1)
    reorder_level: float = Field(ge=0, multiple_of=1)
    opening_stock: float = Field(0, ge=0, multiple_of=1)
    received_quantity: float = Field(0, ge=0, multiple_of=1)
    consumed_quantity: float = Field(0, ge=0, multiple_of=1)
    wasted_quantity: float = Field(0, ge=0, multiple_of=1)
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("Inventory period end precedes start")
        return self


def validate_inventory_refs(db, payload):
    if not db.execute("SELECT 1 FROM restaurant_locations WHERE location_id=?", (payload.location_id,)).fetchone():
        raise HTTPException(422, "Unknown location")
    if not db.execute("SELECT 1 FROM menu_items WHERE item_id=?", (payload.item_id,)).fetchone():
        raise HTTPException(422, "Unknown item")


@router.post("/inventory")
def add_inventory(payload: InventoryUpdate, user=Depends(business)):
    with database.connection() as db:
        validate_inventory_refs(db, payload)
        identity = db.execute("""INSERT INTO inventory_records(location_id,item_id,stock_quantity,reorder_level,
            opening_stock,received_quantity,consumed_quantity,wasted_quantity,period_start,period_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", tuple(payload.model_dump(mode="json").values())).lastrowid
    database.audit("inventory_created", user["id"], "inventory", identity, payload.model_dump(mode="json"))
    return {"inventory_id": identity}


@router.put("/inventory/{inventory_id}")
def edit_inventory(inventory_id: int, payload: InventoryUpdate, user=Depends(business)):
    with database.connection() as db:
        validate_inventory_refs(db, payload)
        cursor = db.execute("""UPDATE inventory_records SET location_id=?,item_id=?,stock_quantity=?,
            reorder_level=?,opening_stock=?,received_quantity=?,consumed_quantity=?,wasted_quantity=?,
            period_start=?,period_end=?,updated_at=CURRENT_TIMESTAMP WHERE inventory_id=?""",
            (*payload.model_dump(mode="json").values(), inventory_id))
        if not cursor.rowcount:
            raise HTTPException(404, "Inventory record not found")
    database.audit("inventory_updated", user["id"], "inventory", inventory_id, payload.model_dump(mode="json"))
    return {"success": True}


@router.get("/wastage/records")
def wastage_records(location_id: int | None = None, limit: int = Query(100, ge=1, le=500),
                    offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    from fast_apis.routes.dynamic import frame, records as dataframe_records, scope
    data = frame("wastage")
    allowed = scope(user, location_id)
    if allowed is not None:
        data = data[data.Location_ID.isin(allowed)]
    data = data.sort_values("Wastage_Date", ascending=False)
    with database.connection() as db:
        if allowed is None:
            managed = rows(db.execute("SELECT * FROM wastage_overrides ORDER BY id DESC LIMIT 100"))
        else:
            marks = ",".join("?" for _ in allowed)
            managed = rows(db.execute(f"SELECT * FROM wastage_overrides WHERE location_id IN ({marks}) ORDER BY id DESC LIMIT 100",
                                      tuple(allowed)))
    return {"total": len(data), "records": dataframe_records(data.iloc[offset:offset + limit]),
            "managed_records": managed, "source": "clean_processed_parquet_plus_live_managed_records"}


class WastageCreate(BaseModel):
    item_id: int
    location_id: int
    wastage_date: str
    quantity_wasted: float = Field(ge=0)
    cost_impact: float = Field(ge=0)
    reason: str = Field(min_length=2)


def validate_wastage(db, payload):
    try:
        date.fromisoformat(payload.wastage_date)
    except ValueError as exc:
        raise HTTPException(422, "Invalid wastage date") from exc
    item = db.execute("SELECT cost FROM menu_items WHERE item_id=?", (payload.item_id,)).fetchone()
    if item is None:
        raise HTTPException(422, "Unknown item_id")
    if not db.execute("SELECT 1 FROM restaurant_locations WHERE location_id=?",
                      (payload.location_id,)).fetchone():
        raise HTTPException(422, "Unknown location_id")
    expected_cost = round(float(item[0]) * payload.quantity_wasted, 2)
    if abs(payload.cost_impact - expected_cost) > .01:
        raise HTTPException(422, f"Cost impact must equal item cost × wasted quantity ({expected_cost:.2f})")


@router.post("/wastage/records")
def add_wastage(payload: WastageCreate, user=Depends(business)):
    with database.connection() as db:
        validate_wastage(db, payload)
        identity = db.execute("""INSERT INTO wastage_overrides(item_id,location_id,wastage_date,quantity_wasted,
            cost_impact,reason,created_by) VALUES(?,?,?,?,?,?,?)""",
            (payload.item_id, payload.location_id, payload.wastage_date, payload.quantity_wasted,
             payload.cost_impact, payload.reason, user["id"])).lastrowid
    database.audit("wastage_record_created", user["id"], "wastage", identity, payload.model_dump())
    return {"id": identity, "live_aggregate_updated": True,
            "analytics_recomputed": False, "forecast_retrained": False}


@router.put("/wastage/records/{record_id}")
def edit_wastage(record_id: int, payload: WastageCreate, user=Depends(business)):
    with database.connection() as db:
        validate_wastage(db, payload)
        changed = db.execute("""UPDATE wastage_overrides SET item_id=?,location_id=?,wastage_date=?,
            quantity_wasted=?,cost_impact=?,reason=? WHERE id=?""",
            (payload.item_id, payload.location_id, payload.wastage_date, payload.quantity_wasted,
             payload.cost_impact, payload.reason, record_id)).rowcount
        if not changed:
            raise HTTPException(404, "Managed wastage record not found")
    database.audit("wastage_record_updated", user["id"], "wastage", record_id, payload.model_dump())
    return {"success": True, "live_aggregate_updated": True,
            "analytics_recomputed": False, "forecast_retrained": False}


@router.get("/jobs")
def jobs(user=Depends(auth.current_user)):
    with database.connection() as db:
        return rows(db.execute("SELECT * FROM analytics_runs ORDER BY id DESC LIMIT 100"))


class JobRequest(BaseModel):
    job_name: str


@router.post("/jobs")
def start_job(payload: JobRequest, tasks: BackgroundTasks, user=Depends(admin)):
    if payload.job_name not in job_service.JOBS:
        raise HTTPException(422, "Unknown job type")
    identity = job_service.enqueue(payload.job_name, user["id"])
    tasks.add_task(job_service.execute, identity, payload.job_name, user["id"])
    return {"job_id": identity, "status": "QUEUED", "job_name": payload.job_name}


@router.get("/jobs/{job_id}")
def job(job_id: int, user=Depends(auth.current_user)):
    with database.connection() as db:
        result = db.execute("SELECT * FROM analytics_runs WHERE id=?", (job_id,)).fetchone()
    if not result:
        raise HTTPException(404, "Job not found")
    return dict(result)


@router.get("/models/versions")
def versions(user=Depends(auth.current_user)):
    with database.connection() as db:
        return rows(db.execute("SELECT * FROM model_versions ORDER BY id DESC"))


@router.get("/audit-logs")
def audit_logs(limit: int = Query(100, ge=1, le=500), user=Depends(admin)):
    with database.connection() as db:
        return rows(db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)))
