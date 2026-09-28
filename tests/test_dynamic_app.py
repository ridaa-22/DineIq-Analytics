"""End-to-end API checks against generated cleaned artifacts and isolated app state."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from fast_apis import database
from fast_apis.main import app
from fast_apis.services import auth_service
from fast_apis.services import job_service


class DynamicAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_db = database.DB_PATH
        database.DB_PATH = Path(cls.temp.name) / "app.sqlite3"
        cls.client = TestClient(app)
        for role, locations in (("ADMIN", []), ("MANAGER", []), ("REGIONAL_MANAGER", [1]), ("ANALYST", [])):
            profile, error = auth_service.register(role, f"{role.lower()}@test.local", "test-password-123", role, locations)
            assert not error, error
            response = cls.client.post("/api/auth/login", json={"email": profile["email"], "password": "test-password-123"})
            assert response.status_code == 200
            setattr(cls, role.lower(), {"Authorization": "Bearer " + response.json()["token"]})

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls.original_db
        cls.temp.cleanup()

    def test_auth_and_roles(self):
        self.assertEqual(self.client.get("/api/dashboard/executive").status_code, 401)
        self.assertEqual(self.client.get("/api/users", headers=self.analyst).status_code, 403)
        self.assertEqual(self.client.get("/api/users", headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get("/api/analytics/basket", headers=self.regional_manager).status_code, 403)
        fresh = self.client.post("/api/auth/login", json={"email": "analyst@test.local",
            "password": "test-password-123"}).json()["token"]
        header = {"Authorization": "Bearer " + fresh}
        self.assertEqual(self.client.post("/api/auth/logout", headers=header).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=header).status_code, 401)

    def test_region_scope(self):
        whole = self.client.get("/api/dashboard/executive", headers=self.admin).json()
        region = self.client.get("/api/dashboard/executive", headers=self.regional_manager).json()
        self.assertLess(region["orders"], whole["orders"])
        self.assertEqual(self.client.get("/api/dashboard/executive?location_id=2",
                                         headers=self.regional_manager).status_code, 403)
        self.assertEqual([row["location_id"] for row in self.client.get("/api/locations",
                          headers=self.regional_manager).json()], [1])
        orders = self.client.get("/api/analytics/orders?limit=10", headers=self.regional_manager)
        self.assertEqual(orders.status_code, 200)
        self.assertTrue(all(row["Location_ID"] == 1 for row in orders.json()["orders"]))
        self.assertEqual(self.client.get("/api/analytics/orders?location_id=2",
                                         headers=self.regional_manager).status_code, 403)

    def test_orders_are_paginated_and_cancelled_have_no_sales_revenue(self):
        first = self.client.get("/api/analytics/orders?limit=5&status=Cancelled", headers=self.admin).json()
        second = self.client.get("/api/analytics/orders?limit=5&offset=5&status=Cancelled", headers=self.admin).json()
        self.assertEqual(len(first["orders"]), 5)
        self.assertNotEqual(first["orders"][0]["Order_ID"], second["orders"][0]["Order_ID"])
        self.assertTrue(all(row["Net_Revenue"] is None for row in first["orders"]))

    def test_corrected_economics(self):
        data = self.client.get("/api/dashboard/executive", headers=self.admin).json()
        self.assertGreater(data["revenue"], 0)
        self.assertAlmostEqual(data["aov"], round(data["revenue"] / data["orders"], 2), places=2)
        self.assertGreater(data["contribution"], 0)

    def test_comparison_and_what_if(self):
        comparison = self.client.get("/api/models/comparison?limit=100", headers=self.analyst).json()
        self.assertGreaterEqual(comparison["total"], 100)
        self.assertEqual(len(comparison["forecasts"]), 100)
        prediction = self.client.post("/api/what-if", headers=self.manager,
            json={"item_id": 1, "price_change_percent": 10, "demand_change_percent": -5})
        self.assertEqual(prediction.status_code, 200)
        self.assertTrue(prediction.json()["is_estimate"])
        logs = self.client.get("/api/audit-logs", headers=self.admin).json()
        self.assertTrue(any(row["action"] == "what_if" for row in logs))
        live = self.client.post("/api/models/forecast/predict?location_id=1", headers=self.regional_manager)
        self.assertEqual(live.status_code, 200)
        self.assertTrue(live.json()["is_estimate"])
        self.assertEqual(self.client.post("/api/models/forecast/predict?location_id=2",
            headers=self.regional_manager).status_code, 403)

    def test_export_is_authenticated_and_audited(self):
        path = "/api/exports/menu?format=csv"
        self.assertEqual(self.client.get(path).status_code, 401)
        csv_response = self.client.get(path, headers=self.admin)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(b"Net_Revenue" if b"Net_Revenue" in csv_response.content else b"revenue", csv_response.content)
        self.assertEqual(self.client.get("/api/exports/menu?format=xlsx", headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get("/api/exports/basket", headers=self.regional_manager).status_code, 403)
        logs = self.client.get("/api/audit-logs", headers=self.admin).json()
        self.assertTrue(any(row["action"] == "report_export" for row in logs))

    def test_live_modules(self):
        for path in ("/api/analytics/menu", "/api/analytics/customers", "/api/analytics/wastage",
                     "/api/analytics/pricing", "/api/analytics/promotions", "/api/analytics/anomalies",
                     "/api/analytics/recommendations", "/api/analytics/basket",
                     "/api/analytics/channels", "/api/analytics/locations",
                     "/api/analytics/churn", "/api/analytics/wastage/forecast",
                     "/api/analytics/customers/profiles"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=self.analyst).status_code, 200)

    def test_management_writes_are_authorized_and_audited(self):
        self.assertEqual(self.client.post("/api/menu/categories", headers=self.analyst,
            json={"category_name": "Test category"}).status_code, 403)
        category = self.client.post("/api/menu/categories", headers=self.manager,
            json={"category_name": "Test category"})
        self.assertEqual(category.status_code, 200)
        category_id = category.json()["category_id"]
        item_payload = {"item_name": "Test item", "category_id": category_id,
                        "base_price": 350, "cost": 180, "description": "Test", "is_available": True}
        item = self.client.post("/api/menu/items", headers=self.manager, json=item_payload)
        self.assertEqual(item.status_code, 200)
        item_id = item.json()["item_id"]
        self.assertFalse(item.json()["historical_data_recomputed"])
        provisional = self.client.get(f"/api/analytics/menu/{item_id}", headers=self.manager)
        self.assertEqual(provisional.status_code, 200)
        self.assertEqual(provisional.json()["sales"], 0)
        self.assertTrue(provisional.json()["insufficient_history"])
        self.assertEqual(provisional.json()["classification"], "Low Performer")
        self.assertTrue(any(row["item_id"] == item_id for row in
                            self.client.get("/api/pricing/history", headers=self.manager).json()))
        inventory = self.client.post("/api/inventory", headers=self.manager,
            json={"location_id": 1, "item_id": item_id, "stock_quantity": 20,
                  "reorder_level": 5})
        self.assertEqual(inventory.status_code, 200)
        self.assertEqual(self.client.get("/api/inventory?location_id=2",
            headers=self.regional_manager).status_code, 403)
        before_wastage = self.client.get("/api/analytics/wastage", headers=self.manager).json()["total_cost"]
        waste_payload = {"item_id": item_id, "location_id": 1, "wastage_date": "2025-12-01",
                         "quantity_wasted": 2, "cost_impact": 360, "reason": "Overproduction"}
        self.assertEqual(self.client.post("/api/wastage/records", headers=self.manager,
            json={**waste_payload, "cost_impact": 1}).status_code, 422)
        waste = self.client.post("/api/wastage/records", headers=self.manager, json=waste_payload)
        self.assertEqual(waste.status_code, 200)
        self.assertFalse(waste.json()["analytics_recomputed"])
        self.assertTrue(waste.json()["live_aggregate_updated"])
        after_wastage = self.client.get("/api/analytics/wastage", headers=self.manager).json()["total_cost"]
        self.assertAlmostEqual(after_wastage - before_wastage, 360, places=2)
        self.assertTrue(any(row["id"] == waste.json()["id"] for row in
                            self.client.get("/api/wastage/records?location_id=1&limit=1",
                                headers=self.regional_manager).json()["managed_records"]))
        actions = {row["action"] for row in self.client.get("/api/audit-logs", headers=self.admin).json()}
        self.assertTrue({"category_created", "menu_item_created", "inventory_created",
                         "wastage_record_created"}.issubset(actions))

    def test_recommendation_evidence_and_job_lifecycle(self):
        result = self.client.get("/api/analytics/recommendations", headers=self.admin)
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertTrue(body["recommendations"])
        self.assertTrue(all(row["evidence"] and row["priority"] in
                            {"Low", "Medium", "High", "Critical"}
                            for row in body["recommendations"]))
        self.assertEqual(self.client.post("/api/jobs", headers=self.analyst,
            json={"job_name": "basket_rules"}).status_code, 403)
        self.assertEqual(self.client.post("/api/jobs", headers=self.admin,
            json={"job_name": "unknown"}).status_code, 422)
        with database.connection() as db:
            actor_id = db.execute("SELECT id FROM users WHERE email='admin@test.local'").fetchone()[0]
        job_id = job_service.enqueue("basket_rules", actor_id)
        with database.connection() as db:
            self.assertEqual(db.execute("SELECT status FROM analytics_runs WHERE id=?",
                                        (job_id,)).fetchone()[0], "QUEUED")
        with patch.object(job_service.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout="rules written", stderr="")):
            job_service.execute(job_id, "basket_rules", actor_id)
        with database.connection() as db:
            job = db.execute("SELECT * FROM analytics_runs WHERE id=?", (job_id,)).fetchone()
            self.assertEqual(job["status"], "COMPLETED")
            self.assertIsNotNone(job["started_at"])
            self.assertIsNotNone(job["ended_at"])
            self.assertGreaterEqual(job["duration_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
