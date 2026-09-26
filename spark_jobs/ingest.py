"""Typed raw ingestion. Does not deduplicate, repair, exclude, or clean records."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType
from spark_jobs.schemas import SCHEMAS, ENUMS, PK, VERSION, required_ids


class IngestionError(ValueError):
    """Input or environment failure with an actionable message."""


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def create_spark(name="DineIQ-Ingestion"):
    java = shutil.which("java")
    if not os.environ.get("JAVA_HOME") and java:
        os.environ["JAVA_HOME"] = str(Path(java).resolve().parents[1])
    if not os.environ.get("JAVA_HOME") and not java:
        raise IngestionError("Java 17/21 is required: configure JAVA_HOME or put java on PATH")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ["PYSPARK_PYTHON"] = sys.executable
    try:
        spark = (SparkSession.builder.master("local[2]").appName(name)
                 .config("spark.driver.host", "127.0.0.1").config("spark.driver.bindAddress", "127.0.0.1")
                 .config("spark.sql.session.timeZone", "Asia/Karachi")
                 .config("spark.sql.shuffle.partitions", "4")
                 .config("spark.sql.csv.parser.columnPruning.enabled", "false")
                 .config("spark.ui.enabled", "false").getOrCreate())
        spark.sparkContext.setLogLevel("ERROR")
        return spark
    except Exception as exc:
        raise IngestionError(f"Spark could not start; check Java 17/21 and local JVM resources: {exc}") from exc


def json_write(path, payload):
    path = Path(path).resolve()
    if any(path.is_relative_to(root) for root in (ROOT / "data/raw", ROOT / "Dineiq_Dataset_RM")):
        raise IngestionError(f"Refusing to write a report into preserved raw data: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_table(spark, table, paths):
    if table not in SCHEMAS:
        raise IngestionError(f"Unknown contract entity: {table}")
    paths = [Path(p).resolve() for p in paths]
    if not paths or len(set(paths)) != len(paths):
        raise IngestionError(f"{table}: provide a nonempty list of distinct input files")
    header = None
    for path in paths:
        if not path.is_file():
            raise IngestionError(f"{table}: missing source file {path}")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            current = next(reader, [])
            try:
                for record in reader:
                    if len(record) != len(current):
                        raise IngestionError(f"{table}: malformed CSV record near line {reader.line_num} in {path.name}; expected {len(current)} fields, found {len(record)}")
            except csv.Error as exc:
                raise IngestionError(f"{table}: invalid CSV quoting in {path.name}: {exc}") from exc
        expected = SCHEMAS[table].fieldNames()
        if len(set(current)) != len(current) or set(current) != set(expected):
            raise IngestionError(f"{table}: invalid columns in {path.name}; expected {expected}, found {current}")
        if header is not None and current != header:
            raise IngestionError(f"{table}: column order must match across all input files")
        header = current
    string_schema = StructType([StructField(c, StringType(), True) for c in header])
    try:
        raw = spark.read.options(header=True, mode="FAILFAST", enforceSchema=False, multiLine=True, escape='"').schema(string_schema).csv([p.as_uri() for p in paths])
        expressions, bad = [], []
        for field in SCHEMAS[table]:
            c = F.col(field.name)
            kind = field.dataType.simpleString()
            cast = c if kind == "string" else c.try_cast(kind)
            invalid = c.isNotNull() & cast.isNull()
            if kind == "bigint":
                invalid = c.isNotNull() & (~c.rlike(r"^[+-]?\d+$") | cast.isNull())
            elif kind.startswith("decimal"):
                invalid = c.isNotNull() & (~c.rlike(r"^[+-]?\d+(\.\d{1,2})?$") | cast.isNull())
            elif kind == "date":
                invalid = c.isNotNull() & (~c.rlike(r"^\d{4}-\d{2}-\d{2}$") | cast.isNull())
            elif kind == "timestamp":
                invalid = c.isNotNull() & (~c.rlike(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+]05:00$") | cast.isNull())
            expressions.append(cast.alias(field.name))
            bad.append(F.sum(F.when(invalid, 1).otherwise(0)).alias(field.name))
        stats = raw.agg(F.count("*").alias("_rows"), *bad).first().asDict()
        if stats["_rows"] == 0:
            raise IngestionError(f"{table}: input has a header but no records")
        invalid_fields = {k: v for k, v in stats.items() if k != "_rows" and v}
        if invalid_fields:
            raise IngestionError(f"{table}: invalid source types {invalid_fields}; fix input types before loading")
        typed = raw.select(*expressions).cache()
        checks = []
        for column in required_ids(table):
            checks.append(F.sum(F.when(F.col(column).isNull() | (F.col(column) <= 0), 1).otherwise(0)).alias(column))
        for (entity, column), allowed in ENUMS.items():
            if entity == table:
                checks.append(F.sum(F.when(F.col(column).isNull() | ~F.col(column).isin(*allowed), 1).otherwise(0)).alias("enum_" + column))
        violations = {k: v for k, v in typed.agg(*checks).first().asDict().items() if v}
        if violations:
            typed.unpersist()
            raise IngestionError(f"{table}: missing/nonpositive required IDs or unsupported enums: {violations}")
        return typed, {"rows": stats["_rows"], "schema_version": VERSION, "schema": typed.schema.jsonValue(),
                       "files": [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)} for p in paths],
                       "input_files": len(paths), "input_partitions": typed.rdd.getNumPartitions(),
                       "type_violations": 0, "required_id_enum_violations": 0}
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"{table}: CSV/Spark read failed for {[p.name for p in paths]}; check CSV shape/quoting and JVM resources: {str(exc)[:600]}") from exc


def load_dataset(spark, data_root=ROOT / "data/raw/phase1-v1"):
    root = Path(data_root).resolve()
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IngestionError(f"Missing/invalid raw manifest at {root}; generate a completed raw version first") from exc
    if manifest.get("dataset_version") != VERSION:
        raise IngestionError(f"Unsupported dataset version: {manifest.get('dataset_version')}; expected {VERSION}")
    frames, summaries = {}, {}
    for table in SCHEMAS:
        path = root / f"{table}.csv"
        expected = manifest.get("files", {}).get(path.name)
        if not path.is_file() or expected is None or sha256(path) != expected.get("sha256"):
            raise IngestionError(f"{table}: missing file or raw provenance/hash mismatch at {path}")
        frames[table], summaries[table] = load_table(spark, table, [path])
        if summaries[table]["rows"] != manifest["counts"].get(table):
            raise IngestionError(f"{table}: row count does not match raw manifest")
        print(f"Loaded {table}: {summaries[table]['rows']:,} rows", flush=True)
    return frames, summaries, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/raw/phase1-v1")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/ingestion_summary.json")
    parser.add_argument("--demonstrate-multifile", action="store_true")
    args = parser.parse_args()
    spark = None
    start = time.perf_counter()
    try:
        spark = create_spark()
        frames, tables, manifest = load_dataset(spark, args.data_root)
        inferred = spark.read.options(header=True, inferSchema=True, multiLine=True, escape='"').csv((args.data_root.resolve() / "Restaurants.csv").as_uri())
        summary = {"status": "PASS", "phase": 2, "dataset_version": VERSION, "spark_version": spark.version,
                   "data_root": str(args.data_root.resolve()), "tables": tables,
                   "inference_demonstration": {"table": "Restaurants", "rows": inferred.count(), "schema": inferred.schema.jsonValue()},
                   "raw_records_unchanged": True, "analytics_eligible": False,
                   "note": "Range, duplicates, missing non-ID values, and business relationships are assessed in Phase 3"}
        if args.demonstrate_multifile:
            with tempfile.TemporaryDirectory(prefix="dineiq-ingest-") as directory:
                parts = [Path(directory) / f"part{i}.csv" for i in range(2)]
                with (args.data_root.resolve() / "Order_Items.csv").open(encoding="utf-8", newline="") as source:
                    header = source.readline()
                    with parts[0].open("w", encoding="utf-8", newline="") as a, parts[1].open("w", encoding="utf-8", newline="") as b:
                        a.write(header); b.write(header)
                        for i, line in enumerate(source):
                            (a if i < 500000 else b).write(line)
                demo, evidence = load_table(spark, "Order_Items", parts)
                if evidence["rows"] != tables["Order_Items"]["rows"]:
                    raise IngestionError("Multi-file demonstration lost or added rows")
                summary["multifile_demonstration"] = evidence
                demo.unpersist()
        summary["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        json_write(args.report, summary)
        print(f"Phase 2 gate PASS: {args.report}", flush=True)
    except Exception as exc:
        json_write(args.report, {"status": "FAIL", "phase": 2, "error": str(exc)[:1200]})
        parser.exit(1, f"Ingestion stopped: {exc}\n")
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    main()
