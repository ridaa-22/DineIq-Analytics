"""Create local demo accounts with generated passwords; never ships fixed credentials."""

import json
import secrets

from fast_apis import database
from fast_apis.services import auth_service


def seed():
    credentials = []
    for role, locations in [("ADMIN", []), ("MANAGER", []), ("REGIONAL_MANAGER", [1, 2]), ("ANALYST", [])]:
        email = f"{role.lower()}@dineiq.local"
        password = secrets.token_urlsafe(18)
        result, error = auth_service.register(role.replace("_", " ").title(), email, password, role, locations)
        if error and "already exists" not in error:
            raise RuntimeError(error)
        if result:
            credentials.append({"role": role, "email": email, "password": password, "locations": locations})
    if credentials:
        path = database.PROJECT_ROOT / "data" / "demo_credentials.json"
        path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
        print(f"Created {len(credentials)} accounts. Credentials: {path}")
    else:
        print("Demo accounts already exist; credentials were not changed.")
    with database.connection() as db:
        for name, version, algorithm, metrics_file, path in [
            ("python_location_forecast", "python-location-rf-v3", "RandomForestRegressor",
             "python_metrics.json", "Models/integrated/python_forecast.joblib"),
            ("spark_location_forecast", "spark-location-selected-v4", "Spark MLlib model selection",
             "spark_selection_metrics.json", None),
            ("customer_rfm_segmentation", "rfm-kmeans-v4", "StandardScaler + KMeans",
             "customer_segment_metrics.json", "Models/integrated/customer_rfm_kmeans.joblib"),
            ("weekly_wastage_forecast", "weekly-wastage-hgb-v5", "HistGradientBoostingRegressor + Classifier",
             "wastage_metrics.json", "Models/integrated/wastage_weekly_model.joblib")]:
            file = database.PROJECT_ROOT / "Models" / "integrated" / metrics_file
            metrics = file.read_text(encoding="utf-8") if file.exists() else "{}"
            if name == "spark_location_forecast" and file.exists():
                path = json.loads(metrics).get("model_path")
            available = bool(path and (database.PROJECT_ROOT / path).is_file()) if path and path.endswith(".joblib") else bool(path and (database.PROJECT_ROOT / path).exists())
            db.execute("""INSERT OR IGNORE INTO model_versions(model_name,version,algorithm,trained_at,dataset_version,
                metrics_json,model_path,is_active) VALUES(?,?,?,datetime('now'),?,?,?,?)""",
                (name, version, algorithm, "phase1-v1-clean-v3", metrics, path, int(available)))
            db.execute("UPDATE model_versions SET is_active=? WHERE model_name=? AND version=?",
                       (int(available), name, version))
            db.execute("UPDATE model_versions SET is_active=0 WHERE model_name=? AND version<>?",
                       (name, version))


if __name__ == "__main__":
    seed()
