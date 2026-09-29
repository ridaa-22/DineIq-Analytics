# Five-million-line local scale run — 2026-09-29

## Fixture and environment

`scripts/make_scale_fixture.py` streamed five copies of the verified phase1-v1 Orders and Order_Items tables into the ignored `reports/nfr_scale/raw_5m/` directory. Each later copy receives a disjoint order and line ID range; line-to-order references are remapped together. Other tables retain their schema and original rows. The fixture manifest records the source manifest SHA-256 and file hashes. The authoritative `data/raw/phase1-v1/` and `data/processed/phase1-v1/` directories were not changed. This is a stress fixture with repeated historical patterns, not an independent new five-million-order business scenario. Ratings and wastage were not multiplied; their references remain valid, but their coverage relative to scaled sales changes.

Host: Dell OptiPlex 790, Intel Core i5-2400 (4 cores), 8.47 GB physical RAM, Windows 10 19045, local PySpark 4.0.2. Raw fixture files total 203,004,278 bytes; processed fixture files total 202,388,309 bytes at the time of the check. These are disk bytes, not peak memory.

| Stage | Command / evidence | Measured wall time | Result |
|---|---|---:|---|
| Fixture generation | `python -m scripts.make_scale_fixture --factor 5 --output reports/nfr_scale/raw_5m` | 76.349 s | 5,000,000 line rows, 500,400 order header rows |
| Spark typed ingestion and validation | `python -m spark_jobs.ingest --data-root reports/nfr_scale/raw_5m --report reports/nfr_scale/ingestion_summary.json` | 109.211 s from ingestion report | PASS; 5,000,000 lines, zero type and required-ID/enum violations |
| Existing Pandas cleaner, isolated paths | `python -c "from pathlib import Path; import Python_Pipeline.build_processed as m; m.RAW=Path('reports/nfr_scale/raw_5m').resolve(); m.OUT=Path('reports/nfr_scale/processed_5m').resolve(); m.build()"` | 102.597 s on timed repeat | 4,799,820 clean completed lines; 2,529 quarantine records |
| Existing Spark multi-table SQL, default heap | `python -c "from pathlib import Path; from spark_jobs.processed_sql import run; run(Path('reports/nfr_scale/processed_5m').resolve(), Path('reports/nfr_scale/spark_sql_5m').resolve())"` | Not recorded | FAIL: Java heap space in stage 34 |
| Same Spark SQL, `SPARK_DRIVER_MEMORY=4g` | `$env:SPARK_DRIVER_MEMORY='4g'; python -c "from pathlib import Path; from spark_jobs.processed_sql import run; run(Path('reports/nfr_scale/processed_5m').resolve(), Path('reports/nfr_scale/spark_sql_5m').resolve())"` | 558.712 s on timed repeat | PASS; 4,799,820 joined rows |

The Spark ingestion report records one input partition for the 5M-line CSV. The cleaner persisted 20 location partitions. During the initial cleaner run, Windows reported at least 1,713.9 MB peak Python working set; during the first configured Spark SQL run, at least 3,602.4 MB peak Java working set was observed. These are sampled process high-water observations, not complete host memory traces. The timed SQL repeat overlapped a separate Spark regression test on the same host, so 558.712 seconds is a contended local wall time, not a clean throughput benchmark.

## Reconciliation and SQL outputs

The clean pipeline reports 5,000,000 raw lines and 4,799,820 eligible completed lines. The 200,180 difference includes cancelled orders and quarantined/invalid records under the existing cleaner contract. The scaled Spark SQL validation reports 4,799,820 joined rows and 4,799,820 distinct `Order_Item_ID` values, so the multi-table joins did not multiply line grain. Missing price, price mismatch, missing promotion, and missing dimension counters are all zero.

| Financial measure | Spark integrated SQL | Authoritative clean sales | Difference |
|---|---:|---:|---:|
| Net revenue | 7,554,196,848.75 | 7,554,196,848.77 | 0.02 |
| Cost | 3,800,190,476.30 | 3,800,190,476.30 | 0.00 |
| Contribution | 3,754,006,372.45 | 3,754,006,372.45 | 0.00 |

The existing SQL emitted 150 menu rows, 20 location rows, 480 location/hour rows, 10 category rows, 20 campaign rows, 100 high-wastage rows, and 5 channel rows. See `reports/nfr_scale/spark_sql_5m/integration_validation.json` and CSV outputs.

## Interpretation

The current architecture completed a local 5M-line ingestion, clean transformation, grain-safe Spark integration, validation, and SQL run without algorithm redesign. A 4 GB Spark driver heap was needed on this 8 GB host; the default heap failed. The one-partition CSV read and single-host fixture do not establish distributed throughput, concurrent-user capacity, or larger-than-5M headroom. No 99% availability conclusion follows from this scale run.
