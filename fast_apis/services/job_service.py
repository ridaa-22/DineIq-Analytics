"""Allow-listed local processing jobs with durable lifecycle status."""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone

from fast_apis import database

JOBS = {
    "spark_sql": ("spark_jobs.processed_sql", "spark"),
    "spark_forecast": ("spark_jobs.train_location_forecast", "spark"),
    "basket_rules": ("Python_Pipeline.build_basket_rules", "python"),
    "customer_segments": ("Python_Pipeline.train_customer_segments", "python"),
    "wastage_forecast": ("Python_Pipeline.train_wastage_forecast", "python"),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def enqueue(job_name, actor_id):
    if job_name not in JOBS:
        raise ValueError("Unknown job type")
    with database.connection() as db:
        identity = db.execute("""INSERT INTO analytics_runs(job_name,status,started_at,dataset_version,details_json)
            VALUES(?,'QUEUED',NULL,'phase1-v1-clean-v3',?)""",
            (job_name, json.dumps({"requested_by": actor_id, "queued_at": now()}))).lastrowid
    database.audit("job_queued", actor_id, "job", identity, {"job_name": job_name})
    return identity


def execute(job_id, job_name, actor_id):
    module, interpreter = JOBS[job_name]
    executable = sys.executable
    if interpreter == "spark":
        candidate = database.PROJECT_ROOT / ".venv-spark" / "Scripts" / "python.exe"
        if candidate.is_file():
            executable = str(candidate)
    started = time.monotonic()
    with database.connection() as db:
        db.execute("UPDATE analytics_runs SET status='RUNNING',started_at=? WHERE id=?", (now(), job_id))
    database.audit("job_started", actor_id, "job", job_id, {"job_name": job_name})
    try:
        completed = subprocess.run([executable, "-m", module], cwd=database.PROJECT_ROOT,
                                   capture_output=True, text=True, timeout=1800, check=False)
        status = "COMPLETED" if completed.returncode == 0 else "FAILED"
        details = {"exit_code": completed.returncode,
                   "stdout_tail": completed.stdout[-3000:], "stderr_tail": completed.stderr[-3000:]}
        if status == "COMPLETED" and job_name == "spark_forecast":
            metrics_path = database.PROJECT_ROOT / "Models" / "integrated" / "spark_selection_metrics.json"
            if metrics_path.is_file():
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                details["model_path"] = metrics.get("model_path")
                details["model_save_error"] = metrics.get("save_error")
                if metrics.get("save_error") or not metrics.get("model_path"):
                    status = "COMPLETED_WITH_WARNINGS"
            else:
                status = "COMPLETED_WITH_WARNINGS"
                details["model_save_error"] = "Spark selection metrics were not written"
    except Exception as exc:
        status = "FAILED"
        details = {"error": f"{type(exc).__name__}: {exc}"}
    with database.connection() as db:
        db.execute("""UPDATE analytics_runs SET status=?,ended_at=?,duration_seconds=?,details_json=? WHERE id=?""",
                   (status, now(), round(time.monotonic() - started, 3), json.dumps(details), job_id))
    database.audit("job_finished", actor_id, "job", job_id, {"status": status, "job_name": job_name})
    if status in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}:
        from fast_apis.routes.dynamic import frame, customer_segment_artifact
        frame.cache_clear()
        customer_segment_artifact.cache_clear()
