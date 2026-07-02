# Azure Data Factory

Metadata-driven ingestion pipeline `PL_Load_RAW`:
- **ForEach** over a file->table mapping array (9 items)
- One **parameterized Copy** activity: source `DS_Blob_CSV` (param `fileName`),
  sink `DS_Snow_RAW` (param `tableName`)
- **Blob staging enabled** (required by the Snowflake connector's bulk COPY)
- **Idempotent** via pre-copy `TRUNCATE TABLE RAW.@{item().table}`
- Authenticates to Snowflake as least-privilege `ADF_SVC`

See `screenshots/` for the build.
