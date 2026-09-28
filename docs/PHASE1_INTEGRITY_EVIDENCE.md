# Phase 1 integrity and security fixes

Management create and update requests share typed validation for menu prices and cost, promotion dates and targets, and inventory references and whole, nonnegative item quantities. SQLite inventory triggers reject unknown item and location IDs on direct inserts and updates. The legacy Express file was moved to `DineiqFrantend/server.legacy.js`, outside the `/app` static mount.

The cleaner writes `data/processed/phase1-v1/rejections.jsonl` with record identifier, source table, rule, reason, and quarantine action. It rejects nonfinite numeric inputs, fractional sale quantities, unknown channels and references, and impossible wastage balances before writing clean Parquet. The existing raw dataset is unchanged. The cleaner test runs against temporary output with injected invalid raw values.

The existing export regression exposed a pandas dtype selector error in the installed dependency set. Its selector now uses pandas' supported `string` dtype name.

Limitations: Existing SQLite tables were not rebuilt to add native foreign keys; inventory triggers enforce those two references for new and updated records. Legacy orphan rows, if present, require a separate migration. Promotions have no location field in the current schema, so there is no location reference to validate. Inventory quantities are item counts; the API has no separate unit field.
