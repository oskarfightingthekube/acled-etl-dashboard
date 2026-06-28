## Layered Architecture (Bronze → Silver → Gold)

**Core rule:** closer to source = more data stored. Closer to report = more filtered.

### Bronze
- Append-only, raw data as-is from API
- Never modify, never delete files
- Serves as immutable archive / reprocessing safety net

### Silver
- Single source of truth (one record per entity, latest version)
- Typing (string → int, string → date)
- Deduplication (latest timestamp wins)
- Removal of deleted/invalid records
- Format: Parquet (columnar, compressed)

### Gold
- Star schema (fact + dimension tables)
- Aggregations, joins, calculated metrics
- Reporting datasets optimized for BI tools
- Only columns needed for business questions