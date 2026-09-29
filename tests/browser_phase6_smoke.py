"""Real browser smoke test for the grain/horizon controls against a local API."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def request(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10) as response:
        return json.load(response)


def run(phase7=False):
    with tempfile.TemporaryDirectory() as temporary:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment["DINEIQ_AUTH_DB"] = str(Path(temporary) / "browser.sqlite3")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "fast_apis.main:app",
                                   "--host", "127.0.0.1", "--port", str(port)],
                                  cwd=ROOT, env=environment, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, creationflags=flags)
        try:
            for _ in range(80):
                if server.poll() is not None:
                    raise RuntimeError("API server stopped before browser test")
                try:
                    request(origin + "/api/health")
                    break
                except Exception:
                    time.sleep(0.25)
            else:
                raise TimeoutError("API server did not become ready")
            request(origin + "/api/register", {"username": "Browser Forecast", "email": "browser@test.local",
                                               "password": "test-password-123"})
            login = request(origin + "/api/login", {"email": "browser@test.local",
                                                      "password": "test-password-123"})
            with sync_playwright() as playwright:
                chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
                browser = playwright.chromium.launch(headless=True,
                                                     executable_path=str(chrome) if chrome.is_file() else None)
                try:
                    context = browser.new_context()
                    context.add_init_script("localStorage.setItem('authToken', " + json.dumps(login["token"]) +
                                            "); localStorage.setItem('user', " +
                                            json.dumps(json.dumps(login["user"])) + ");")
                    page = context.new_page()
                    page.goto(origin + "/app/analytics-ml.html")
                    try:
                        page.locator("#grain-forecast").wait_for(timeout=15000)
                    except Exception:
                        raise AssertionError(f"Forecast form absent at {page.url}: {page.locator('body').inner_text()[:500]}")
                    checked = []
                    for grain, horizon in (("location", 1), ("item", 7), ("category", 30)):
                        page.locator("#grain-forecast [name=grain]").select_option(grain)
                        page.locator("#grain-forecast [name=entity_id]").fill("1")
                        page.locator("#grain-forecast [name=horizon]").select_option(str(horizon))
                        page.locator("#grain-forecast button").click()
                        page.wait_for_function("([grain, horizon]) => document.querySelector('#grain-result')?.textContent.includes(grain.toUpperCase() + ' 1 · ' + horizon + ' day(s)')", arg=[grain, horizon], timeout=30000)
                        content = page.locator("#grain-result").inner_text()
                        assert "Test MAE" in content and "Baseline" in content
                        assert page.locator("#grain-result tbody tr").count() == horizon
                        checked.append(f"{grain}:{horizon}")
                    if phase7:
                        page.goto(origin + "/app/Menu-management.html")
                        page.locator("#slow-filter").wait_for(timeout=30000)
                        page.locator("#slow-filter").select_option("HIDDEN_OPPORTUNITY")
                        page.wait_for_url("**slow_status=HIDDEN_OPPORTUNITY", timeout=30000)
                        page.locator("#slow-filter").wait_for(timeout=30000)
                        assert page.locator(".content-wrapper tbody tr").count() == 25
                        assert "HIDDEN_OPPORTUNITY" in page.locator(".content-wrapper").inner_text()
                        checked.append("menu:slow_filter")
                        page.goto(origin + "/app/index.html?view=recommendations")
                        page.get_by_text("slow_moving", exact=True).first.wait_for(timeout=30000)
                        checked.append("recommendations:slow_moving")
                    print(json.dumps({"browser": "Chromium", "checked": checked, "passed": True}))
                finally:
                    browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)


if __name__ == "__main__":
    run()
