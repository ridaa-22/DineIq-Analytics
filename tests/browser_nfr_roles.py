"""Live four-role login, scope, action, export and responsive Chromium checks."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fast_apis import database
from fast_apis.services.auth_service import register


ROLES = ("ADMIN", "MANAGER", "REGIONAL_MANAGER", "ANALYST")


def run():
    with tempfile.TemporaryDirectory() as temporary:
        db_path = Path(temporary) / "roles.sqlite3"
        original = database.DB_PATH
        database.DB_PATH = db_path
        try:
            for role in ROLES:
                _, error = register(role.title(), f"{role.lower()}@nfr.local", "test-password-123",
                                    role, [1] if role == "REGIONAL_MANAGER" else [])
                if error:
                    raise RuntimeError(error)
        finally:
            database.DB_PATH = original
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment["DINEIQ_AUTH_DB"] = str(db_path)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "fast_apis.main:app",
            "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        try:
            for _ in range(80):
                if server.poll() is not None:
                    raise RuntimeError("API server exited")
                try:
                    with urlopen(origin + "/api/health", timeout=2):
                        break
                except Exception:
                    time.sleep(.25)
            else:
                raise TimeoutError("API server did not start")
            results = {}
            with sync_playwright() as playwright:
                chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
                browser = playwright.chromium.launch(headless=True,
                    executable_path=str(chrome) if chrome.is_file() else None)
                try:
                    signup_context = browser.new_context()
                    signup = signup_context.new_page()
                    registration_requests = []
                    signup.on("request", lambda request: registration_requests.append(request.url)
                              if request.url.endswith("/api/register") else None)
                    signup.goto(origin + "/app/register.html")
                    signup.locator("#username").fill("New Analyst")
                    signup.locator("#email").fill("new-analyst@nfr.local")
                    signup.locator("#password").fill("123456")
                    signup.locator("#registerForm input[type=checkbox]").check()
                    signup.locator("#registerForm button[type=submit]").click()
                    assert signup.locator("#password").evaluate("element => element.validity.tooShort")
                    assert not registration_requests
                    signup.locator("#password").fill("long-enough-password")
                    with signup.expect_response("**/api/register", timeout=15000) as response:
                        signup.locator("#registerForm button[type=submit]").click()
                    assert response.value.status == 200
                    results["registration"] = {"short_password_blocked_before_request": True,
                        "valid_signup_status": response.value.status}
                    signup_context.close()
                    for role in ROLES:
                        context = browser.new_context(viewport={"width": 1366, "height": 768}, accept_downloads=True)
                        page = context.new_page()
                        page.goto(origin + "/app/Login.html")
                        page.locator("#email").fill(f"{role.lower()}@nfr.local")
                        page.locator("#password").fill("test-password-123")
                        page.locator("#loginForm button[type=submit]").click()
                        page.wait_for_url("**/app/index.html", timeout=15000)
                        page.get_by_text("Executive Dashboard", exact=True).first.wait_for(timeout=30000)
                        assert page.locator('a[href="reports.html"]').count() > 0
                        token = page.evaluate("localStorage.getItem('authToken')")
                        headers = {"Authorization": "Bearer " + token}
                        def status(path, method="GET", data=None):
                            return context.request.fetch(origin + path, method=method,
                                headers={**headers, **({"Content-Type": "application/json"} if data else {})},
                                data=json.dumps(data) if data else None).status
                        expected_business = 200 if role in {"ADMIN", "MANAGER"} else 403
                        expected_admin = 200 if role == "ADMIN" else 403
                        result = {"login": True, "dashboard": True, "reports_nav": True,
                            "admin_users_status": status("/api/users"),
                            "manage_category_status": status("/api/menu/categories", "POST",
                                {"category_name": f"NFR {role}"}),
                            "export_status": status("/api/exports/menu?location_id=1&format=csv"),
                            "location_2_status": status("/api/dashboard/executive?location_id=2")}
                        assert result["admin_users_status"] == expected_admin
                        assert result["manage_category_status"] == expected_business
                        assert result["export_status"] == 200
                        assert result["location_2_status"] == (403 if role == "REGIONAL_MANAGER" else 200)
                        if role == "REGIONAL_MANAGER":
                            assert status("/api/exports/menu?location_id=2&format=csv") == 403
                        page.goto(origin + "/app/reports.html")
                        page.get_by_text("Authenticated Reports", exact=True).first.wait_for(timeout=30000)
                        result["reports_page"] = True
                        results[role] = result
                        context.close()
                    responsive = {}
                    for width, height in ((1366, 768), (390, 844)):
                        context = browser.new_context(viewport={"width": width, "height": height})
                        page = context.new_page()
                        page.goto(origin + "/app/Login.html")
                        page.locator("#email").wait_for(timeout=10000)
                        responsive[f"{width}x{height}"] = {"login_form_visible": page.locator("#loginForm").is_visible(),
                            "login_horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > window.innerWidth")}
                        assert responsive[f"{width}x{height}"]["login_form_visible"]
                        page.locator("#email").fill("analyst@nfr.local")
                        page.locator("#password").fill("test-password-123")
                        page.locator("#loginForm button[type=submit]").click()
                        page.wait_for_url("**/app/index.html", timeout=15000)
                        page.get_by_text("Executive Dashboard", exact=True).first.wait_for(timeout=30000)
                        responsive[f"{width}x{height}"]["dashboard_visible"] = True
                        responsive[f"{width}x{height}"]["dashboard_horizontal_overflow"] = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                        page.goto(origin + "/app/menu-management.html")
                        page.locator("#category-filter").wait_for(timeout=30000)
                        responsive[f"{width}x{height}"]["menu_filter_visible"] = page.locator("#category-filter").is_visible()
                        responsive[f"{width}x{height}"]["menu_horizontal_overflow"] = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                        context.close()
                    results["responsive"] = responsive
                finally:
                    browser.close()
            target = ROOT / "reports" / "nfr_roles_browser.json"
            target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(results, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)


if __name__ == "__main__":
    run()
