"""Short local health-check observation; never represents production uptime."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as temporary:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = os.environ.copy()
        env["DINEIQ_AUTH_DB"] = str(Path(temporary) / "health.sqlite3")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "fast_apis.main:app",
            "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        observations = []
        try:
            for _ in range(80):
                if server.poll() is not None:
                    raise RuntimeError("Health server exited before startup")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(.25)
            else:
                raise TimeoutError("Health server did not start")
            start = datetime.now(timezone.utc)
            for index in range(30):
                sample_start = time.perf_counter()
                ok = False
                error = None
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                        ok = response.status == 200 and json.load(response).get("status") == "ok"
                except Exception as exc:
                    error = type(exc).__name__
                observations.append({"at_utc": datetime.now(timezone.utc).isoformat(),
                    "ok": ok, "error_type": error})
                if index < 29:
                    time.sleep(max(0, 2 - (time.perf_counter() - sample_start)))
            end = datetime.now(timezone.utc)
            output = {"environment": "temporary local uvicorn process", "start_utc": start.isoformat(),
                "end_utc": end.isoformat(), "elapsed_seconds": (end - start).total_seconds(),
                "planned_interval_seconds": 2, "checks": len(observations),
                "successful_checks": sum(row["ok"] for row in observations),
                "observations": observations,
                "interpretation": "Short health-check sample; 99% service availability remains NOT VERIFIED"}
            target = ROOT / "reports" / "nfr_availability_smoke.json"
            target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({key: value for key, value in output.items() if key != "observations"}, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
