"""Small application-state database; transaction data remain in processed files."""

import csv
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("DINEIQ_AUTH_DB", PROJECT_ROOT / "data" / "app_users.sqlite3"))
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "phase1-v1"
ROLES = ("ADMIN", "MANAGER", "REGIONAL_MANAGER", "ANALYST")


def _csv(name):
    path = RAW_DIR / name
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def initialize(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password_hash TEXT NOT NULL, password_salt TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id),
          expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS revoked_tokens (
          jti TEXT PRIMARY KEY, expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS roles (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS user_roles (
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          role_name TEXT NOT NULL REFERENCES roles(name),
          PRIMARY KEY(user_id,role_name)
        );
        CREATE TABLE IF NOT EXISTS user_locations (
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          location_id INTEGER NOT NULL,
          PRIMARY KEY(user_id,location_id)
        );
        CREATE TABLE IF NOT EXISTS restaurant_locations (
          location_id INTEGER PRIMARY KEY, location_name TEXT NOT NULL,
          city TEXT, address TEXT, opening_date TEXT, is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS menu_categories (
          category_id INTEGER PRIMARY KEY, category_name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS menu_items (
          item_id INTEGER PRIMARY KEY, item_name TEXT NOT NULL,
          category_id INTEGER REFERENCES menu_categories(category_id),
          base_price REAL NOT NULL, cost REAL NOT NULL,
          description TEXT, is_available INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS pricing_history (
          pricing_id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES menu_items(item_id),
          price REAL NOT NULL, effective_date TEXT NOT NULL,
          changed_by INTEGER REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS promotions (
          promotion_id INTEGER PRIMARY KEY, promotion_name TEXT NOT NULL,
          discount_percent REAL NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
          applicable_item_id INTEGER, applicable_category_id INTEGER,
          location_id INTEGER REFERENCES restaurant_locations(location_id)
        );
        CREATE TABLE IF NOT EXISTS inventory_records (
          inventory_id INTEGER PRIMARY KEY, location_id INTEGER NOT NULL,
          item_id INTEGER NOT NULL, stock_quantity REAL NOT NULL,
          reorder_level REAL NOT NULL, opening_stock REAL NOT NULL DEFAULT 0,
          received_quantity REAL NOT NULL DEFAULT 0, consumed_quantity REAL NOT NULL DEFAULT 0,
          wasted_quantity REAL NOT NULL DEFAULT 0, period_start TEXT, period_end TEXT,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TRIGGER IF NOT EXISTS inventory_refs_insert BEFORE INSERT ON inventory_records
        WHEN NOT EXISTS (SELECT 1 FROM menu_items WHERE item_id=NEW.item_id)
          OR NOT EXISTS (SELECT 1 FROM restaurant_locations WHERE location_id=NEW.location_id)
        BEGIN SELECT RAISE(ABORT, 'Unknown inventory item or location'); END;
        CREATE TRIGGER IF NOT EXISTS inventory_refs_update BEFORE UPDATE OF item_id,location_id ON inventory_records
        WHEN NOT EXISTS (SELECT 1 FROM menu_items WHERE item_id=NEW.item_id)
          OR NOT EXISTS (SELECT 1 FROM restaurant_locations WHERE location_id=NEW.location_id)
        BEGIN SELECT RAISE(ABORT, 'Unknown inventory item or location'); END;
        CREATE TABLE IF NOT EXISTS wastage_overrides (
          id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL,
          location_id INTEGER NOT NULL, wastage_date TEXT NOT NULL,
          quantity_wasted REAL NOT NULL, cost_impact REAL NOT NULL,
          reason TEXT NOT NULL, created_by INTEGER REFERENCES users(id),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS model_versions (
          id INTEGER PRIMARY KEY, model_name TEXT NOT NULL, version TEXT NOT NULL,
          algorithm TEXT, trained_at TEXT, dataset_version TEXT,
          metrics_json TEXT, model_path TEXT, is_active INTEGER NOT NULL DEFAULT 0,
          UNIQUE(model_name,version)
        );
        CREATE TABLE IF NOT EXISTS analytics_runs (
          id INTEGER PRIMARY KEY, job_name TEXT NOT NULL, status TEXT NOT NULL,
          started_at TEXT, ended_at TEXT, duration_seconds REAL,
          dataset_version TEXT, details_json TEXT
        );
        CREATE TABLE IF NOT EXISTS recommendations (
          id INTEGER PRIMARY KEY, recommendation_type TEXT NOT NULL,
          entity_id TEXT, action TEXT NOT NULL, priority TEXT NOT NULL,
          evidence_json TEXT NOT NULL, reason TEXT,
          rule_version TEXT NOT NULL, generated_at TEXT NOT NULL,
          dataset_version TEXT NOT NULL, rec_key TEXT UNIQUE,
          location_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS predictions (
          id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, actual REAL,
          prediction REAL NOT NULL, model_name TEXT NOT NULL,
          model_version TEXT, dataset_version TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
          action TEXT NOT NULL, entity TEXT, entity_id TEXT,
          timestamp INTEGER NOT NULL, details_json TEXT
        );
        CREATE TABLE IF NOT EXISTS exports (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          report_name TEXT NOT NULL, format TEXT NOT NULL,
          created_at INTEGER NOT NULL, row_count INTEGER
        );
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    if "is_active" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    promotion_columns = {row[1] for row in db.execute("PRAGMA table_info(promotions)")}
    if "location_id" not in promotion_columns:
        db.execute("ALTER TABLE promotions ADD COLUMN location_id INTEGER REFERENCES restaurant_locations(location_id)")
    recommendation_columns = {row[1] for row in db.execute("PRAGMA table_info(recommendations)")}
    if "rec_key" not in recommendation_columns:
        db.execute("ALTER TABLE recommendations ADD COLUMN rec_key TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS recommendations_rec_key ON recommendations(rec_key)")
    if "location_id" not in recommendation_columns:
        db.execute("ALTER TABLE recommendations ADD COLUMN location_id INTEGER")
    db.executemany("INSERT OR IGNORE INTO roles(name) VALUES(?)", ((name,) for name in ROLES))
    # Existing demo accounts had no roles. Give them the least privileged role.
    db.execute("""INSERT OR IGNORE INTO user_roles(user_id,role_name)
                  SELECT id,'ANALYST' FROM users WHERE id NOT IN (SELECT user_id FROM user_roles)""")
    if db.execute("SELECT COUNT(*) FROM restaurant_locations").fetchone()[0] == 0:
        db.executemany("INSERT INTO restaurant_locations(location_id,location_name,city,address,opening_date) VALUES(?,?,?,?,?)",
                       [(int(r["Location_ID"]), r["Location_Name"], r["City"], r["Address"], r["Opening_Date"])
                        for r in _csv("Restaurants.csv")])
    if db.execute("SELECT COUNT(*) FROM menu_categories").fetchone()[0] == 0:
        db.executemany("INSERT INTO menu_categories(category_id,category_name) VALUES(?,?)",
                       [(int(r["Category_ID"]), r["Category_Name"]) for r in _csv("Menu_Categories.csv")])
    if db.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
        first_prices = {}
        for row in _csv("Pricing_History.csv"):
            first_prices.setdefault(int(row["Item_ID"]), float(row["Price"]))
        db.executemany("""INSERT INTO menu_items(item_id,item_name,category_id,base_price,cost,description,is_available)
                          VALUES(?,?,?,?,?,?,?)""",
                       [(int(r["Item_ID"]), r["Item_Name"], int(r["Category_ID"]),
                         first_prices.get(int(r["Item_ID"]), max(0.0, float(r["Base_Price"]))),
                         float(r["Cost"]), r["Description"], int(r["Is_Available"]))
                        for r in _csv("Menu_Items.csv")])
    if db.execute("SELECT COUNT(*) FROM pricing_history").fetchone()[0] == 0:
        db.executemany("INSERT INTO pricing_history(pricing_id,item_id,price,effective_date) VALUES(?,?,?,?)",
                       [(int(r["Pricing_ID"]), int(r["Item_ID"]), float(r["Price"]), r["Effective_Date"])
                        for r in _csv("Pricing_History.csv")])
    if db.execute("SELECT COUNT(*) FROM promotions").fetchone()[0] == 0:
        db.executemany("""INSERT INTO promotions(promotion_id,promotion_name,discount_percent,start_date,end_date,applicable_item_id,applicable_category_id)
                          VALUES(?,?,?,?,?,?,?)""",
                       [(int(r["Promotion_ID"]), r["Promotion_Name"], float(r["Discount_Percent"]),
                         r["Start_Date"], r["End_Date"], int(r["Applicable_Item_ID"]), int(r["Applicable_Category_ID"]))
                        for r in _csv("Promotions.csv")])
    if db.execute("SELECT COUNT(*) FROM inventory_records").fetchone()[0] == 0:
        db.executemany("""INSERT INTO inventory_records(inventory_id,location_id,item_id,stock_quantity,reorder_level,
            opening_stock,received_quantity,consumed_quantity,wasted_quantity,period_start,period_end)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            [(int(r["Inventory_ID"]), int(r["Location_ID"]), int(r["Item_ID"]), float(r["Stock_Quantity"]),
              float(r["Reorder_Level"]), float(r["Opening_Stock"]), float(r["Received_Quantity"]),
              float(r["Consumed_Quantity"]), float(r["Wasted_Quantity"]), r["Period_Start"], r["Period_End"])
             for r in _csv("Inventory.csv")])
    db.commit()


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    try:
        initialize(db)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def audit(action, user_id=None, entity=None, entity_id=None, details=None):
    import json
    with connection() as db:
        db.execute("INSERT INTO audit_logs(user_id,action,entity,entity_id,timestamp,details_json) VALUES(?,?,?,?,?,?)",
                   (user_id, action, entity, str(entity_id) if entity_id is not None else None,
                    int(time.time()), json.dumps(details or {}, sort_keys=True)))
