"""Run the full generator gate and persist evidence; no Spark or ML execution."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from test_phase1_generator import ROOT, check
from generate_phase1 import generate


def main():
    dataset = ROOT / "data/raw/phase1-v1"
    reports = ROOT / "reports/phase1"
    reports.mkdir(parents=True, exist_ok=True)
    print("Checking full-scale generated relationships and scenarios...", flush=True)
    result = check(dataset)
    print("Full-scale assertions PASS", flush=True)
    baseline = json.loads((dataset / "manifest.json").read_text())
    print("Generating isolated repeat for byte reproducibility...", flush=True)
    with tempfile.TemporaryDirectory(prefix="dineiq-phase1-repro-") as temporary:
        temp_path = Path(temporary).resolve()
        if not temp_path.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("Temporary output escaped expected temporary root")
        repeat = temp_path / "repeat"
        actual = generate(repeat)
        if actual != baseline:
            raise AssertionError("Repeat manifest/hash mismatch")
    print("Reproducibility PASS", flush=True)
    note = (ROOT / "data/raw/README.md").read_text(encoding="utf-8")
    verified = []
    for line in note.splitlines():
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) == 3 and re.fullmatch(r"[0-9a-f]{64}", parts[2]):
            path = ROOT / parts[0]
            if path.stat().st_size != int(parts[1]) or hashlib.sha256(path.read_bytes()).hexdigest() != parts[2]:
                raise AssertionError(f"Original source modified: {parts[0]}")
            verified.append(parts[0])
    if len(verified) != 15:
        raise AssertionError("Incomplete Phase 0 preservation baseline")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != "af1f1d90927efc452ba74188937139b69a9783c4":
        raise AssertionError("Git HEAD changed")
    if subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip() != "2264b453577f2217803616992d018bfbbbf75c6c":
        raise AssertionError("Git tree changed")
    (reports / "acceptance.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (reports / "reproducibility.json").write_text(json.dumps({"status": "PASS", "seed": 42, "matching_manifest": True,
        "csv_files_compared": len(baseline["files"]), "files": baseline["files"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (reports / "source_preservation.txt").write_text("PASS: all 15 Phase 0 original files unchanged; Git HEAD and tree unchanged\n" + "\n".join(verified) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    print("Phase 1 acceptance gate PASS; evidence saved in reports/phase1", flush=True)


if __name__ == "__main__":
    main()
