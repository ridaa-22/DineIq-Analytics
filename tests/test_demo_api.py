"""Smoke checks for protected legacy report routes retained during migration."""

import unittest
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from fast_apis.main import app
from fast_apis import database
from fast_apis.services import auth_service


class DemoApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.previous_db = database.DB_PATH
        database.DB_PATH = Path(cls.temp.name) / "app.sqlite3"
        cls.client = TestClient(app)
        profile, error = auth_service.register("Analyst", "analyst@legacy.test", "test-password-123")
        assert not error, error
        token = cls.client.post("/api/auth/login", json={"email": profile["email"],
            "password": "test-password-123"}).json()["token"]
        cls.headers = {"Authorization": "Bearer " + token}

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls.previous_db
        cls.temp.cleanup()

    def test_required_endpoints(self):
        for path in (
            "/api/health", "/api/dashboard/summary", "/api/menu/intelligence",
            "/api/customers/segments", "/api/forecast", "/api/model-comparison",
            "/api/recommendations", "/api/models/status", "/docs",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)

    def test_existing_reports_are_exposed_without_invented_metrics(self):
        summary = self.client.get("/api/dashboard/summary", headers=self.headers).json()
        self.assertTrue(summary["available"])
        self.assertIsNone(summary["total_revenue"])
        self.assertGreater(summary["segmented_customers"], 0)
        comparison = self.client.get("/api/model-comparison", headers=self.headers).json()
        self.assertEqual(comparison["summary"]["case_count"], comparison["total"])
        self.assertLess(comparison["total"], comparison["summary"]["srs_minimum_cases"])

    def test_pagination_and_report_allowlist(self):
        segments = self.client.get("/api/customers/segments?limit=3&offset=3", headers=self.headers).json()
        self.assertEqual(len(segments["records"]), 3)
        self.assertGreater(segments["total"], 3)
        self.assertEqual(self.client.get("/api/reports/menu-intelligence/download", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/api/reports/not-allowed/download", headers=self.headers).status_code, 404)

    def test_frontend_served_by_same_app(self):
        self.assertEqual(self.client.get("/app/index.html").status_code, 200)
        self.assertEqual(self.client.get("/app/operations-orders.html").status_code, 200)
        self.assertEqual(self.client.get("/app/assets/js/dineiq-demo.js").status_code, 200)


if __name__ == "__main__":
    unittest.main()
