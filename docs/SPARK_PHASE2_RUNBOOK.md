# Phase 2 ingestion runbook

Environment: Python 3.13 and PySpark 4.0.2, Java 17 (Java 21 also supported by this Spark release). Dependencies are isolated in `.venv-spark/`; they are not installed into the original Python environment. Version compatibility and CSV parsing behavior are based on the [Apache Spark 4.0.2 documentation](https://spark.apache.org/docs/4.0.2/) and [CSV documentation](https://spark.apache.org/docs/4.0.2/sql-data-sources-csv.html).

From the Git project root in PowerShell:

```powershell
python -m venv .venv-spark
.\.venv-spark\Scripts\python.exe -m pip install -r requirements-spark.txt
.\.venv-spark\Scripts\python.exe -B tests/test_spark_ingestion.py
.\.venv-spark\Scripts\python.exe -B spark_jobs/ingest.py --demonstrate-multifile
```

Java must be on PATH or JAVA_HOME must point to its installation directory. Jobs derive the canonical project root from their own file location, not the current directory or notebook state. By default they load `data/raw/phase1-v1/` with its hash manifest. `--data-root` and `--report` accept explicit alternatives. A different schema version is rejected.

All eleven entities have explicit typed schemas in `spark_jobs/schemas.py`: positive required IDs, decimal(18,2) PKR fields, integer portions, dates, and offset timestamps. The CSV transport layer first reads strings so invalid casts cannot disappear into null values. Strict headers/record shape, source hashes, lexical types, required IDs, and enumerations must pass. Field order may differ from the contract for a single source, but must match between files in a multi-file load.

The job preserves null non-ID values, duplicates, cancellations, negative numeric quantities/prices, and out-of-range numeric ratings for later assessment. Blank date fields are represented as null; a nonempty unparsable date is a fatal ingestion error. Typed raw frames are not analytics-approved. No record is filled, dropped, clipped, or deduplicated.

The inference demonstration independently reads Restaurants with Spark inference and records its actual inferred schema; this does not replace the explicit contract. Multi-file demonstration copies the complete million-line Order_Items CSV into two temporary CSV files and loads both together. Counts must match the original. Temporary files are removed afterward; raw files are untouched. This is source-file handling, not a processed-Parquet partition strategy.

`reports/ingestion_summary.json` records PASS/FAIL, input hashes, schemas, rows, files, input partitions, inference, multi-file evidence, and elapsed time. CSV header/shape failures, empty data, invalid types, required IDs, unknown enums, missing manifests/files, and Spark startup failures stop with actionable messages and a nonzero exit. A failed run replaces its report with FAIL rather than leaving a stale PASS report.

Phase 2 does not assess foreign-key/business relationships or clean dirty values. Those require the subsequent gates.
