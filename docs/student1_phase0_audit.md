# Student 1 — Phase 0 audit and workspace baseline

Audit date: 2026-09-26 (Asia/Karachi). Scope: repository discovery, baseline capture, implementation ledger, and proposed paths only.

The audit reads existing implementation and data without executing or changing them. The only additions are this report and `data/raw/README.md`, the two documentation artifacts requested by Phase 0. No later phase, dependency installation, notebook execution, data migration, cleaning, training, commit, or history rewrite is performed.

## Starting point

- Canonical project root: `C:/Users/Aptech/Desktop/DINEIQ/DineIq-Analytics/`, the existing Git repository.
- Workspace parent: `C:/Users/Aptech/Desktop/DINEIQ/`.
- HEAD: `af1f1d90927efc452ba74188937139b69a9783c4`.
- HEAD tree: `2264b453577f2217803616992d018bfbbbf75c6c`.
- Starting working-tree changes: modified `DineIq_Dataset.ipynb`; untracked `DineIQ Analytics-Data Science Intelligence Arena_SRS.pdf`.
- Four local commits are visible, all dated 2026-09-26. The commit titled `Data cleaning` has the same tree as its parent; its title is not evidence of cleaning.
- No applicable `AGENTS.md` was found in the repository, workspace, or ancestor directories.

The baseline protects the current working copy, including its existing modifications. It does not reset it to HEAD. File hashes, counts, headers, and a runnable verification procedure are recorded in [the provenance note](../data/raw/README.md).

## Inventory

```text
DINEIQ/
├── DineIQ_Student1_Codex_Spark_Phase_Guide.md
├── DineIq-Analytics.zip
└── DineIq-Analytics/                   canonical project root
    ├── .git/
    ├── README.md
    ├── DineIQ Analytics-Data Science Intelligence Arena_SRS.pdf
    ├── DineIq_Dataset.ipynb
    └── Dineiq_Dataset_RM/             delivered raw snapshot
        ├── Customers.csv
        ├── Inventory.csv
        ├── Menu_Categories.csv
        ├── Menu_Items.csv
        ├── Orders.csv
        ├── Order_Items.csv
        ├── Order_Items.parquet
        ├── Pricing_History.csv
        ├── Promotions.csv
        ├── Ratings.csv
        ├── Restaurants.csv
        └── Wastage.csv
```

The inventory includes hidden files and the archive. Git contains standard metadata/hooks; these are not application modules. The ZIP has the same twelve raw-data files byte-for-byte and no additional analytical implementation. Its notebook source is the same prototype, with different saved state. Do not extract the ZIP over the working tree or treat it as an independent pipeline.

No standalone Spark jobs, Spark SQL scripts, schemas, configuration, cleaned outputs, feature artifacts, models, comparison results, automated tests, processing reports, or application modules were found. The two Phase 0 documentation files are additions to this inventory, not analytical outputs.

## Paths and notebook evidence

Cell numbers are one-based positions in `DineIq_Dataset.ipynb`, not execution counters. Counters are out of sequence and do not prove a fresh sequential run.

| Path | References | Current reality |
|---|---|---|
| `Dineiq_Dataset_RM/` | Delivered data directory | Exists; no notebook source selects it |
| `dineiq_dataset_1M/` | Generator cell 3; reads in cells 4, 6, 14–17; conversion writes in cell 15 | Absent from repository |
| `dineiq_dataset/` | CSV read and Parquet write in cell 8 | Absent from repository |
| `dineiq_dataset_1M/Orders.parquet` | Read in cell 4; creation source in cell 15 | Absent; read precedes creation in a fresh run |
| `dineiq_dataset_1M/Menu_Items.parquet` | Cell 15 | Conversion code exists; output absent |
| `dineiq_dataset_1M/Restaurants.parquet` | Cell 15 | Conversion code exists; output absent |

| Cells | Actual implementation | Observed limitation |
|---|---|---|
| 1–3 | Imports, seeded synthetic generator, CSV/raw Parquet writers | Uses current time; writes another directory; must not run during baseline audit |
| 4, 13, 14 | Three `SparkSession.builder...getOrCreate()` calls | Repeated setup; no reusable job entry point |
| 5 | Counts negative quantities, duplicate orders, null order dates | No cleaning assignment, quarantine, decision log, or cleaned output |
| 6 | Pandas CSV-count loop | Saved `No module named 'pandas'` error |
| 7, 9–11 | Package installation and Java/Conda checks | Environment commands, not a reproducible setup guide; not executed |
| 8 | Raw CSV-to-Parquet conversion | Uses a third path name; no processing |
| 15 | Raw Parquet conversions; Order_Items/Orders/Menu_Items/Restaurants inner joins; city gross revenue | Duplicate headers can multiply lines; cancellation and discounts ignored; no output persistence |
| 16–17 | Identical raw CSV RFM, StandardScaler, KMeans(k=4) | Exact duplicate source; incorrect frequency/monetary eligibility; Student 2 area, inventoried only |
| 18 | Gross line total, year/month/day/hour, unit price minus cost | No persisted features; saved Spark `TaskResultLost` error on final display action |
| 19–22 | Empty cells | No implementation |

The saved cell 5 output reports 150 negative quantities, 80 duplicate order headers, and 30 null order dates. Cell 15 reports 1,001,598 joined rows and city totals. Cells 16–17 print ten RFM/cluster examples each. These are historical notebook outputs, not fresh verified analytical runs against the delivered directory. The earlier full audit reconstructed 1,001,600 joined rows from current CSVs; this discrepancy must be reconciled in the later integration phase, not hidden by copying saved outputs.

Only `Dineiq_Dataset_RM/Order_Items.parquet` is actually delivered. Fresh footer inspection confirms 1,000,000 rows, six columns, one row group, and Quantity minimum -1. It is raw dirty storage, not the processed Parquet required by the SRS. Footer inspection does not establish row-by-row CSV/Parquet equivalence or a successful Spark read.

## Implementation ledger

| Decision | Existing asset / missing capability | Reason and later action |
|---|---|---|
| KEEP | Twelve delivered raw files and existing Git history | Immutable provenance baseline; never silently overwrite |
| KEEP | Eleven-entity generator scaffold and scale/ID conventions | Reuse after Phase 1 contract and relationship repair |
| KEEP | Notebook as historical prototype and saved failure evidence | Preserve; do not present its output as production evidence |
| REPLACE | Ad-hoc environment install cells as execution procedure | Later provide reproducible installation/configuration instructions |
| REPLACE | Repeated Spark initialization and notebook-only execution | Later create a single configured Spark job entry point |
| REPAIR | Three inconsistent data roots and early Orders.parquet read | Resolve input paths against one project root and correct job ordering |
| REPAIR | Generator dates, ratings, campaign, pricing, customer/location relationships | Phase 1 documents and repairs semantics; no repair performed here |
| REPAIR | Raw joins and gross-only revenue/margin expressions | Later clean first, respect discounts/status, and reconcile joins |
| REPAIR | Duplicate RFM/KMeans cells 16–17 | Record for Student 2; do not implement independent Python work in Student 1 phases |
| MISSING | Explicit schemas, comprehensive type/key/business validation | Phase 2–3 work |
| MISSING | Quality report, documented cleaning, quarantine, decision/reconciliation evidence | Phase 3–4 work |
| MISSING | Clean processed Parquet, partition strategy, versioned manifest | Phase 5 work |
| MISSING | All required grain-safe joins and persisted business features | Phase 6–7 work |
| MISSING | Real Spark SQL, EDA/peak outputs, timing evidence | Phase 8 work |
| MISSING | Daily item-location demand dataset and chronological split manifests | Phase 9 work |
| MISSING | Three fitted/evaluated Spark MLlib algorithms, selected saved/versioned model, unseen predictions | Phase 10–11 work |
| MISSING | Executable Spark/data tests, logs, run summary, handoff package | Phase 12–13 work; assertions accompany earlier phases |

This ledger makes no completed-feature claim. Raw row counts and source snippets do not prove ingestion, cleaning, analytics, forecasting, or ML completion.

## Proposed canonical layout

All paths resolve from the canonical Git project root, regardless of shell/notebook working directory. The following is a documented proposal for subsequent phases, not a migration already performed or a claim of team approval.

| Purpose | Canonical path / policy |
|---|---|
| Original raw snapshot | `Dineiq_Dataset_RM/` — retain in place, read-only; identify as `legacy-rm-phase0` |
| Raw provenance index | `data/raw/README.md` — documentation only; contains no copied datasets |
| Newly generated raw versions | `data/raw/<dataset_version>/` — new version, never replace legacy files |
| Clean processed Parquet | `data/processed/<dataset_version>/<entity>/` |
| Processed manifest | `data/processed/<dataset_version>/manifest.json` |
| Quarantine | `data/quarantine/<dataset_version>/<run_id>/<entity>/` |
| Quality/reconciliation/timing evidence | `reports/<dataset_version>/<run_id>/` |
| Spark jobs / SQL | `spark_jobs/`, `spark_sql/` |
| Features / splits / models | `features/<dataset_version>/`, `splits/<dataset_version>/`, `models/spark/<model_version>/` |
| Contract/configuration / tests | `docs/`, `config/`, `tests/` |

Only the two documentation parent directories are created in Phase 0. Empty future implementation directories are not created to imply progress. The guide mixes `processed_data/manifest.json` with `data/processed/`; the proposed layout uses a single manifest under `data/processed/<dataset_version>/` to avoid another competing root. Record any later agreed change explicitly.

Future jobs select one raw version via configuration, never auto-discover conflicting copies. Downstream analytics read manifest-selected processed Parquet after its gate passes; they must fail clearly rather than fall back to legacy raw CSVs. Business units, timezone, allowed statuses, cleaning policy, partition keys, feature formulas, and demand target remain Phase 1 or later decisions.

## Phase 0 checks and acceptance gate

Fresh checks used Python standard-library CSV/JSON/hash/ZIP readers, Parquet footer metadata decoding, and read-only Git commands. No project dependencies were installed and no Spark, generator, or KMeans job was run.

| Gate check | Evidence / outcome |
|---|---|
| Canonical project root identified | Existing Git root documented above |
| Raw/processed/quarantine separation documented | Proposed layout; legacy raw retained in place |
| Recursive repository/workspace inventory captured | Inventory and archive inspection above |
| Current paths, duplication, code/output limitations captured | Cell/path tables and ledger |
| Raw row counts, headers, byte sizes, SHA-256 captured | Provenance note; all eleven CSVs scanned |
| Original files and Git history preserved | PASS after documentation creation: all 15 original file sizes/SHA-256 match; HEAD and tree unchanged |
| No later-phase implementation | Only this audit and the provenance README added |

Executed acceptance results:

```text
PASS: 15 original files unchanged; Git HEAD and tree unchanged
PASS: all 11 documented CSV count/unique-ID baselines match
PASS: workspace ZIP and guide hashes match their documented baselines
PASS: documentation links resolve
```

Final Git status retains the original modified notebook and untracked SRS, plus only `docs/student1_phase0_audit.md` and `data/raw/README.md` as new files. No commit is created.

The verification procedure is the Phase 0 acceptance check, not a later Spark test suite. Phase 0 inventory/provenance checks passed. The layout remains proposed for team adoption; do not claim human approval. Stop at this gate. Phase 1 has not started.
