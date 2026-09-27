# Raw-data provenance — Student 1 Phase 0

Baseline ID: `legacy-rm-phase0`. Recorded: 2026-09-26 (Asia/Karachi).

At the Phase 0 baseline, this directory contained provenance documentation only. The twelve original dataset files remain at `../../Dineiq_Dataset_RM/` relative to this directory. They have not been renamed, moved, copied, cleaned, regenerated, or overwritten. Phase 1 adds a separate generated version under `phase1-v1/`; its contract and generation provenance are independent of the historical snapshot below.

Project root: `C:/Users/Aptech/Desktop/DINEIQ/DineIq-Analytics/`.
Baseline HEAD: `af1f1d90927efc452ba74188937139b69a9783c4`.
Baseline tree: `2264b453577f2217803616992d018bfbbbf75c6c`.
Existing changes before audit: modified notebook; untracked SRS PDF. The baseline below records those working-copy bytes, not HEAD versions.

Generation source is `DineIq_Dataset.ipynb`, cell 3: Pandas/NumPy/Faker, seeds 42, current-time date generation, intended output directory `dineiq_dataset_1M/`. Delivered files are in `Dineiq_Dataset_RM/`. Seed values do not freeze current-time bounds or dependency versions. This is existing synthetic raw data with deliberate defects, not verified clean analytical data.

## Current counts

CSV counts exclude the header; distinct IDs are measured from the first ID column. They do not establish clean primary keys or valid business relationships.

| File | Records | Distinct primary IDs | Duplicate ID excess |
|---|---:|---:|---:|
| Customers.csv | 50040 | 50000 | 40 |
| Inventory.csv | 2000 | 2000 | 0 |
| Menu_Categories.csv | 10 | 10 | 0 |
| Menu_Items.csv | 150 | 150 | 0 |
| Order_Items.csv | 1000000 | 1000000 | 0 |
| Orders.csv | 100080 | 100000 | 80 |
| Pricing_History.csv | 375 | 375 | 0 |
| Promotions.csv | 20 | 20 | 0 |
| Ratings.csv | 100000 | 100000 | 0 |
| Restaurants.csv | 20 | 20 | 0 |
| Wastage.csv | 50000 | 50000 | 0 |

Observed nonempty order timestamps: `2025-09-25 07:36:47.034377` through `2026-09-25 07:28:50.034377`; 30 order timestamps are empty. Other observed empty fields: Customer_Name 120, Rating_Date 33, Promotion_ID 75098. An absent promotion is not automatically invalid.

The Parquet footer reports 1,000,000 rows, six columns, one row group, and Quantity minimum -1. Full row-level equivalence with CSV and fresh Spark execution were not tested in this phase.

## Observed CSV headers

These are observations, not approved explicit schemas, types, units, or cleaning rules.

| Entity | Header order |
|---|---|
| Customers | Customer_ID, Customer_Name, City, Signup_Date, Preferred_Channel |
| Inventory | Inventory_ID, Location_ID, Item_ID, Stock_Quantity, Reorder_Level, Last_Restocked_Date |
| Menu_Categories | Category_ID, Category_Name |
| Menu_Items | Item_ID, Item_Name, Category_ID, Base_Price, Cost, Description, Is_Available |
| Order_Items | Order_Item_ID, Order_ID, Item_ID, Quantity, Unit_Price, Discount_Applied |
| Orders | Order_ID, Customer_ID, Location_ID, Order_DateTime, Channel, Promotion_ID, Order_Status |
| Pricing_History | Pricing_ID, Item_ID, Price, Effective_Date |
| Promotions | Promotion_ID, Promotion_Name, Discount_Percent, Start_Date, End_Date, Applicable_Category_ID |
| Ratings | Rating_ID, Order_ID, Item_ID, Customer_ID, Stars, Rating_Date |
| Restaurants | Location_ID, Location_Name, City, Address, Opening_Date |
| Wastage | Wastage_ID, Item_ID, Location_ID, Wastage_Date, Quantity_Wasted, Cost_Impact, Reason |

## Original-file SHA-256 baseline

Paths are relative to the project root. The table also protects the original notebook, README, and SRS. Hashes are byte-for-byte, so an intentional future edit must not silently replace this historical baseline.

| Project-relative path | Bytes | SHA-256 |
|---|---:|---|
| Dineiq_Dataset_RM/Customers.csv | 2532794 | 8ac41ce649734b707d87e8b926a3de133971b9dbf6085a3bab2581d450fbeeb3 |
| Dineiq_Dataset_RM/Inventory.csv | 57586 | 949367ecedca8e6aa0de335b82a0fc6bd25bf21172e1451617fdf8cdad0aa269 |
| Dineiq_Dataset_RM/Menu_Categories.csv | 147 | 597beccf42d50e0611b2370b82a66f04e063b33c343781a407d0a3450b2efc22 |
| Dineiq_Dataset_RM/Menu_Items.csv | 13471 | 440897e8e7c79450f8b9eaaff1b7119f4dfb47941cd105cad5a29511778b3f98 |
| Dineiq_Dataset_RM/Order_Items.csv | 31117240 | ffee771e7ec866ef6cde35f9988806df6702c444b87188974f60c236842d7623 |
| Dineiq_Dataset_RM/Order_Items.parquet | 8009523 | d73131b8f46926ea10e5a6d9d035ad5e6f3cf463d4cd8c9e3e24dbc122d33f19 |
| Dineiq_Dataset_RM/Orders.csv | 6366223 | a384c0b4e15ac8999700c0bf2c8fad06688c9bab347022028d556bacdb891c46 |
| Dineiq_Dataset_RM/Pricing_History.csv | 15946 | 6a413f6bf33a05293cbe847fb373685e5e6d217dbc98730025cbbfcb16f18728 |
| Dineiq_Dataset_RM/Promotions.csv | 1024 | 677837418f5ae4e20a0f17f0daa3c84e002b59220b01ea7f6631100a2d1f51f9 |
| Dineiq_Dataset_RM/Ratings.csv | 5082429 | 8316d53e06ba74c2d557e9507ff6f398c715bbbf062a1ee334d990cf0db9c6de |
| Dineiq_Dataset_RM/Restaurants.csv | 2093 | c5773b63129b4176c8b145d6ca663b091072dcbc02ea4ea6c95a084309791aa7 |
| Dineiq_Dataset_RM/Wastage.csv | 2461826 | cd084e63c762c45acf6d7e115dbd673bfe2dd14a3258b4b400b42cc0b41cc297 |
| DineIq_Dataset.ipynb | 152101 | c89e5c06d820b02c87b9d843dc93b19553d73c1a90fd5b5b9588995b5503c27d |
| README.md | 109 | 559e2a8b8c6becd0021b48ed182d8dd7b436d52b064235f04c1205c841f37ca0 |
| DineIQ Analytics-Data Science Intelligence Arena_SRS.pdf | 2061416 | d67de19b9e039335bf4250696073654eafb5eea89969a80204dee9c0aca8e7eb |

Workspace-level reference hashes (not pipeline inputs):

- `DineIq-Analytics.zip`: 29406347 bytes; SHA-256 `2cdc70dae915cf255537c2e04f8b9302aaaf0f599529e377a62dac82e720193c`.
- `DineIQ_Student1_Codex_Spark_Phase_Guide.md`: 26404 bytes; SHA-256 `904803756908be89127694d6b984b3ded958e00ac215eed49bbdf1649170efdb`.

## Read-only baseline verifier

Run from the project root in PowerShell. It needs only Python standard library and Git. It checks all fifteen original files and history identifiers; it does not run the generator, notebook, or Spark. A mismatch is a failure requiring investigation, not permission to overwrite the baseline.

```powershell
@'
import hashlib
import pathlib
import re
import subprocess

root = pathlib.Path.cwd()
note = root / "data/raw/README.md"
rows = []
for line in note.read_text(encoding="utf-8").splitlines():
    if not line.startswith("| "):
        continue
    fields = [part.strip() for part in line.split("|")[1:-1]]
    if len(fields) == 3 and re.fullmatch(r"[0-9a-f]{64}", fields[2]):
        rows.append(fields)
if len(rows) != 15:
    raise SystemExit(f"FAIL: expected 15 baseline records, found {len(rows)}")
failures = []
for relative, size, expected in rows:
    path = root / relative
    if not path.is_file():
        failures.append(f"missing: {relative}")
        continue
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if path.stat().st_size != int(size) or digest.hexdigest() != expected:
        failures.append(f"changed: {relative}")
for ref, expected in (
    ("HEAD", "af1f1d90927efc452ba74188937139b69a9783c4"),
    ("HEAD^{tree}", "2264b453577f2217803616992d018bfbbbf75c6c"),
):
    actual = subprocess.check_output(["git", "rev-parse", ref], cwd=root, text=True).strip()
    if actual != expected:
        failures.append(f"history changed: {ref}")
if failures:
    raise SystemExit("FAIL\n" + "\n".join(failures))
print("PASS: 15 original files unchanged; Git HEAD and tree unchanged")
'@ | python -
```

## Future write policy

Retain this baseline in place. New raw generation writes a separate `data/raw/<dataset_version>/`; Phase 1 uses `phase1-v1/`. See [DATA_CONTRACT.md](../../docs/DATA_CONTRACT.md) for the version's fields and declared dirty fixtures. Clean Parquet and its manifest belong in `data/processed/<dataset_version>/`; excluded original records/reasons belong in `data/quarantine/<dataset_version>/<run_id>/`. Processed and quarantine outputs do not exist yet. Downstream jobs will consume the processed manifest after the relevant phase gate, with no fallback to dirty CSVs. See [the Phase 0 audit](../../docs/student1_phase0_audit.md) for the historical layout proposal and ledger.
