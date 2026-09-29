# NFR evidence — 2026-09-29

Statuses apply only to the operation and environment stated. `PASS` means that specific check executed successfully; it is not a claim that every production condition is covered. Phase 11 did not change forecasting algorithms or the authoritative dataset.

| NFR / claim | Status | Evidence and limit |
|---|---|---|
| At least 5,000,000 order lines processed | **PARTIAL** | [Scale report](../reports/NFR_SCALE_REPORT.md): 5M raw lines ingested, 4,799,820 clean completed lines, same Spark multi-table SQL reconciled. Default Spark heap failed; configured 4 GB heap passed on one 8 GB Windows host. One input partition; no distributed or concurrency proof. |
| Five-second prediction/response wording | **NEEDS SRS INTERPRETATION** | The SRS phrase refers to “claim details,” which does not identify a DineIQ operation. Local measurements below distinguish model prediction, API requests, and report export. A single blanket pass would be misleading. |
| Python forecast beats simple baseline | **PASS** | Saved chronological 581-case holdout recomputed: model MAE 70.4840, observed lag-7 MAE 77.0792. |
| Spark forecast beats simple baseline | **PARTIAL** | Same 581-case holdout: Spark MAE 79.2460, observed lag-7 MAE 77.0792. The Spark model loses. |
| Wastage amount forecast beats simple baseline | **PARTIAL** | 6,149 observed-week holdout: model MAE 1.0035, last-observed MAE 0.6528. Model remains `EXPERIMENTAL`. |
| Four-role login, authorization, location scoping and report access | **PARTIAL** | Live Chromium role matrix below covers login/dashboard/reports and selected API actions for all four roles. It is a local task smoke test, not a full usability study with human participants. |
| Browser and responsive behavior | **PARTIAL** | Chromium on Windows at 1366×768 and 390×844: login, dashboard, menu filter visible with no document-level horizontal overflow. Firefox, Safari, Edge, accessibility, interaction quality, and additional pages were not tested. |
| 99% service availability | **NOT VERIFIED** | Local temporary Uvicorn process: 30/30 `/api/health` checks passed over 58.026 seconds. No production monitoring window, failure recovery exercise, or long-running service history exists. |

## Local latency samples

Measured by `python -m scripts.benchmark_nfr` on a Dell OptiPlex 790 (Intel Core i5-2400, 4 cores, 8.47 GB RAM, Windows 10 19045). Sequential FastAPI `TestClient` requests used a temporary SQLite database and the existing clean artifacts. Each API had one warm-up request. There was no browser rendering or network hop in these timings. Raw samples are in `reports/nfr_latency.json`.

| Operation | Samples | p50 | p95 | Maximum |
|---|---:|---:|---:|---:|
| Python next-day live prediction API | 12 | 60.073 ms | 77.932 ms | 84.187 ms |
| Model comparison API | 12 | 29.471 ms | 31.808 ms | 33.387 ms |
| Executive dashboard API | 12 | 46.024 ms | 49.084 ms | 49.359 ms |
| Filtered menu CSV report API | 8 | 3,802.156 ms | 5,142.267 ms | 5,586.563 ms |
| Python model cold artifact load | 1 | 93.823 ms | 93.823 ms | 93.823 ms |
| Warm direct model prediction | 30 | 31.414 ms | 67.983 ms | 93.468 ms |

The cold-load row has one sample, so its p50/p95 are simply that observation. The CSV report exceeded five seconds in this small sample. These numbers do not predict multi-user or remote deployment latency.

## Baselines

`python -m scripts.evaluate_nfr_baselines` recomputed mean absolute error from the saved unchanged holdouts. Python and Spark location results use the same 581 unseen location/day cases and observed lag-7 demand. Wastage uses the last observed wastage as its amount baseline. Values and case counts are in `reports/nfr_baselines.json`. The Spark and wastage comparisons remain unfavorable; no baseline was changed to force a win.

## Four-role live browser matrix

`python tests/browser_nfr_roles.py` launched a temporary local API and used actual Chromium login forms. It checked dashboard and reports pages in the browser, then tested authenticated actions through the browser context. Evidence is in `reports/nfr_roles_browser.json`.

| Role | Login/dashboard/reports | Manage category | List users | Export location 1 | Dashboard location 2 |
|---|---|---:|---:|---:|---:|
| Admin | PASS | 200 | 200 | 200 | 200 |
| Manager | PASS | 200 | 403 | 200 | 200 |
| Regional Manager (assigned location 1) | PASS | 403 | 403 | 200 | 403 |
| Analyst | PASS | 403 | 403 | 200 | 200 |

The Regional Manager's location-2 export also returned 403. The browser UI itself was not exhaustively assessed for whether every role sees only useful controls; this remains a usability limit.

## Availability observation

`python -m scripts.availability_smoke` sampled an isolated local Uvicorn process every two seconds after startup. It recorded 30 successful health responses from 2026-09-29 01:41:45 UTC to 01:42:43 UTC. The 58.026-second sample is in `reports/nfr_availability_smoke.json`. It is insufficient to verify a 99% availability target over any meaningful service period.
