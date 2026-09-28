# API

Base URL: `http://127.0.0.1:8000`. Send `Authorization: Bearer <access_token>` to every endpoint below except health, register, and login. Responses use JSON unless an export is requested.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an Analyst account |
| POST | `/api/auth/login` | Obtain one-hour JWT |
| POST | `/api/auth/logout` | Revoke current JWT and log sign-out |
| GET | `/api/auth/me` | Current roles and locations |
| GET | `/api/dashboard/executive` | Net completed-sales KPIs; optional `location_id`, `date_from`, `date_to` |
| GET | `/api/analytics/orders` | Paginated validated historical orders; optional location, date, channel, status |
| GET | `/api/analytics/menu` | Multifactor item economics and descriptive classes; optional location, category, class |
| GET | `/api/analytics/menu/{item_id}` | Item detail |
| GET | `/api/analytics/customers` | Clean-RFM KMeans segments; optional location, segment |
| GET | `/api/analytics/customers/profiles` | Per-cluster business evidence |
| GET | `/api/analytics/customers/{customer_id}` | Scoped customer spending |
| GET | `/api/analytics/wastage` | Clean wastage summaries |
| GET | `/api/analytics/wastage/forecast` | Experimental next-week item/location risk |
| GET | `/api/analytics/forecast` | Location-day holdout predictions |
| GET | `/api/analytics/pricing` | Equal-window observed economics around genuine historical price changes |
| GET | `/api/analytics/promotions` | Before/during/after campaign economics and trap flag |
| GET | `/api/analytics/anomalies` | Sales spikes, rating bursts, and unusual orders |
| GET | `/api/analytics/channels` | Channel performance comparison |
| GET | `/api/analytics/locations` | Standardized location comparison |
| GET | `/api/analytics/churn` | At-risk customers with recency/decline evidence |
| GET | `/api/analytics/basket` | Item association rules |
| GET | `/api/analytics/recommendations` | Evidence-based deterministic actions |
| GET | `/api/models/comparison` | Independent Spark/Python holdout comparison |
| POST | `/api/models/forecast/predict?location_id={id}` | Audited next-day Python model estimate |
| POST | `/api/what-if` | Estimated item scenario with explicit assumptions |
| GET | `/api/locations` | Scoped location metadata |
| POST/PUT | `/api/locations`, `/api/locations/{id}` | Admin location management |
| GET/PUT | `/api/menu/items`, `/api/menu/items/{id}` | Metadata and authorized edits |
| POST | `/api/menu/items` | Add menu item; historical analytics need refresh |
| GET/POST/PUT | `/api/menu/categories`, `/api/menu/categories/{id}` | Category management |
| GET | `/api/pricing/history` | Effective-price event history |
| GET/PUT | `/api/promotions`, `/api/promotions/{id}` | Promotion metadata and edits |
| POST | `/api/promotions` | Add campaign metadata |
| GET/POST/PUT | `/api/inventory`, `/api/inventory/{id}` | Inventory period records |
| GET/POST/PUT | `/api/wastage/records`, `/api/wastage/records/{id}` | Historical clean records plus separate managed records |
| GET/POST | `/api/users` | Admin user listing and creation |
| PUT | `/api/users/{id}/role` | Admin role, active flag and region assignment |
| GET | `/api/jobs`, `/api/jobs/{id}` | Processing job records |
| POST | `/api/jobs` | Admin starts an allow-listed local job: `spark_sql`, `spark_forecast`, `basket_rules`, `customer_segments`, or `wastage_forecast` |
| GET | `/api/models/versions` | Model metadata |
| GET | `/api/audit-logs` | Admin audit trail |
| GET | `/api/reports/{name}/download` | Allow-listed legacy CSV download, audited |
| GET | `/api/exports/{name}` | Clean current CSV/Excel export; optional `format` and `location_id`, audited |

Legacy endpoints under `/api/dashboard/summary`, `/api/menu/intelligence`, `/api/customers/segments`, `/api/forecast`, `/api/model-comparison`, `/api/recommendations` and `/api/models/status` remain protected for compatibility. They use the older reports and should not be mixed with the cleaned API in an analytical claim. Regional users receive 403 on those unscoped endpoints.

Management endpoints require Manager or Administrator except location/user/role administration, which requires Administrator. Regional managers can read only assigned-location analytics. Managed wastage writes validate item cost, location, and date; they return `live_aggregate_updated: true`, `analytics_recomputed: false`, and `forecast_retrained: false`. The live analytical overlay updates aggregates, while versioned Parquet and the wastage model remain unchanged. Job status can be `QUEUED`, `RUNNING`, `COMPLETED`, `COMPLETED_WITH_WARNINGS`, or `FAILED`; the warning state includes model-save failures.
