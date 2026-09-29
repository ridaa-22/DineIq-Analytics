"""Stream a relationship-preserving scale fixture from the verified raw dataset."""

import argparse
import csv
import hashlib
import json
import shutil
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "phase1-v1"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def replicate(source, target, factor, key, linked_key=None, stride=None):
    """Keep source rows and defects; assign disjoint IDs to later copies."""
    stride = stride or (100_000 if key == "Order_ID" else 1_000_000)
    count = 0
    with target.open("x", encoding="utf-8", newline="") as output:
        writer = None
        for batch in range(factor):
            with source.open(encoding="utf-8", newline="") as input_file:
                reader = csv.DictReader(input_file)
                if writer is None:
                    writer = csv.DictWriter(output, fieldnames=reader.fieldnames, lineterminator="\n")
                    writer.writeheader()
                for row in reader:
                    row[key] = str(int(row[key]) + batch * stride)
                    if linked_key:
                        row[linked_key] = str(int(row[linked_key]) + batch * 100_000)
                    writer.writerow(row)
                    count += 1
    return count


def make(output, factor=5):
    if factor < 1:
        raise ValueError("factor must be positive")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite fixture: {output}")
    if output.is_relative_to(SOURCE):
        raise ValueError("Scale fixture must be outside authoritative raw data")
    source_manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    start = time.perf_counter()
    output.mkdir(parents=True)
    counts = {}
    for name, original_count in source_manifest["counts"].items():
        source = SOURCE / f"{name}.csv"
        target = output / source.name
        if name == "Orders":
            counts[name] = replicate(source, target, factor, "Order_ID")
        elif name == "Order_Items":
            counts[name] = replicate(source, target, factor, "Order_Item_ID", "Order_ID")
        else:
            shutil.copyfile(source, target)
            counts[name] = original_count
    if counts["Order_Items"] != source_manifest["counts"]["Order_Items"] * factor:
        raise AssertionError("Order line count changed unexpectedly")
    files = {path.name: {"bytes": path.stat().st_size, "sha256": digest(path)}
             for path in sorted(output.glob("*.csv"))}
    manifest = {**source_manifest, "counts": counts, "files": files,
        "scale_fixture": {"factor": factor, "source_manifest_sha256": digest(SOURCE / "manifest.json"),
                          "order_id_stride": 100_000, "line_id_stride": 1_000_000,
                          "generation_seconds": round(time.perf_counter() - start, 3)}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "nfr_scale" / "raw_5m")
    parser.add_argument("--factor", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(make(args.output, args.factor)["scale_fixture"], indent=2))
