"""Measure local warmed API and model operations; save raw samples and summaries."""

import json
import platform
import tempfile
import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from fast_apis import database
from fast_apis.main import app
from fast_apis.routes.dynamic import python_forecast_artifact
from fast_apis.services.auth_service import register


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "nfr_latency.json"


def describe(samples):
    ordered = sorted(samples)
    def percentile(p):
        position = (len(ordered) - 1) * p
        lower = int(position)
        return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)
    return {"samples": len(ordered), "p50_ms": round(percentile(.5), 3),
            "p95_ms": round(percentile(.95), 3), "max_ms": round(max(ordered), 3),
            "raw_ms": [round(value, 3) for value in samples]}


def main():
    original = database.DB_PATH
    with tempfile.TemporaryDirectory() as directory:
        database.DB_PATH = Path(directory) / "nfr.sqlite3"
        try:
            user, error = register("NFR Analyst", "nfr@local.test", "test-password-123")
            if error:
                raise RuntimeError(error)
            with TestClient(app) as client:
                token = client.post("/api/login", json={"email": user["email"],
                    "password": "test-password-123"}).json()["token"]
                headers = {"Authorization": "Bearer " + token}
                paths = {
                    "python_live_prediction_api": ("POST", "/api/models/forecast/predict?location_id=1", 12),
                    "comparison_api": ("GET", "/api/models/comparison?limit=100", 12),
                    "dashboard_api": ("GET", "/api/dashboard/executive?location_id=1", 12),
                    "menu_csv_report_api": ("GET", "/api/exports/menu?category_id=1&format=csv", 8),
                }
                results = {}
                for name, (method, path, count) in paths.items():
                    warm = client.request(method, path, headers=headers)
                    if warm.status_code != 200:
                        raise RuntimeError(f"{name}: HTTP {warm.status_code}: {warm.text[:160]}")
                    samples = []
                    for _ in range(count):
                        start = time.perf_counter()
                        response = client.request(method, path, headers=headers)
                        samples.append((time.perf_counter() - start) * 1000)
                        if response.status_code != 200:
                            raise RuntimeError(f"{name}: HTTP {response.status_code}")
                    results[name] = describe(samples)
                python_forecast_artifact.cache_clear()
                start = time.perf_counter()
                artifact = python_forecast_artifact()
                results["model_cold_load"] = describe([(time.perf_counter() - start) * 1000])
                history = pd.read_parquet(ROOT / "data/processed/phase1-v1/location_daily.parquet")
                history = history[history.Location_ID.eq(1)].sort_values("Date")
                next_date = pd.Timestamp(history.Date.iloc[-1]) + pd.Timedelta(days=1)
                features = pd.DataFrame([{"Location_ID": 1, "day_of_week": next_date.dayofweek,
                    "month": next_date.month, "lag_1": float(history.Demand.iloc[-1]),
                    "lag_7": float(history.Demand.iloc[-7]),
                    "rolling_7": float(history.Demand.iloc[-7:].mean())}])[artifact["features"]]
                model = artifact["model"]
                model.predict(features)
                samples = []
                for _ in range(30):
                    start = time.perf_counter()
                    model.predict(features)
                    samples.append((time.perf_counter() - start) * 1000)
                results["model_warm_prediction"] = describe(samples)
            payload = {"host": {"platform": platform.platform(), "processor": platform.processor()},
                "method": "Sequential local TestClient requests; one warm-up per API; no network hop; one cold model load; fixed location 1",
                "operations": results}
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({name: {key: value for key, value in result.items() if key != "raw_ms"}
                for name, result in results.items()}, indent=2))
        finally:
            database.DB_PATH = original


if __name__ == "__main__":
    main()
