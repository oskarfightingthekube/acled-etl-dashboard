-- =============================================================================
-- 10_star_schema.sql — dimensional star schema (fact + conformed dimensions)
-- =============================================================================
-- Turns the wide event fact (gold_events_wide) into a textbook star: one fact
-- table surrounded by dimension tables, joined on natural keys. This is the
-- "schemat gwiazdy" deliverable and the base for the Power BI semantic layer.
--
-- Star:
--   fact_events (grain: one event)
--     ├─ dim_country     (iso              → country, region)
--     ├─ dim_date        (date_key         → year, month, month_name, quarter)
--     ├─ dim_event_type  (sub_event_type   → event_type, disorder_type)
--     ├─ dim_actor       (actor            = actor1)
--     └─ dim_source      (source_scale)
--   (dim_population from 07 joins on iso + year for per-capita.)
--
-- VERIFIED in acled_dev (eu-central-1): fact = 2,669,096 rows; FK integrity =
-- 0 orphan keys (every non-null fact key exists in its dimension).
--
-- Power BI relationships to create (Model view), all 1-to-many (dim → fact):
--   fact_events[iso]            -> dim_country[iso]
--   fact_events[event_date]     -> dim_date[date_key]
--   fact_events[sub_event_type] -> dim_event_type[sub_event_type]
--   fact_events[actor1]         -> dim_actor[actor]
--   fact_events[source_scale]   -> dim_source[source_scale]
-- =============================================================================

-- --- dimensions ---
CREATE TABLE acled_dev.dim_country
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_country/') AS
SELECT iso, arbitrary(country) country, arbitrary(region) region
FROM acled_dev.gold_events_wide WHERE iso IS NOT NULL GROUP BY iso;

CREATE TABLE acled_dev.dim_date
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_date/') AS
SELECT date_key,
       year(date_key)             as year,
       month(date_key)            as month,
       date_format(date_key,'%M') as month_name,
       quarter(date_key)          as quarter
FROM (SELECT DISTINCT event_date date_key FROM acled_dev.gold_events_wide WHERE event_date IS NOT NULL);

CREATE TABLE acled_dev.dim_event_type
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_event_type/') AS
SELECT sub_event_type, arbitrary(event_type) event_type, arbitrary(disorder_type) disorder_type
FROM acled_dev.gold_events_wide WHERE sub_event_type IS NOT NULL GROUP BY sub_event_type;

CREATE TABLE acled_dev.dim_actor
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_actor/') AS
SELECT DISTINCT actor1 as actor FROM acled_dev.gold_events_wide WHERE actor1 IS NOT NULL;

CREATE TABLE acled_dev.dim_source
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_source/') AS
SELECT DISTINCT source_scale FROM acled_dev.gold_events_wide WHERE source_scale IS NOT NULL;

-- --- fact ---
CREATE TABLE acled_dev.fact_events
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/fact_events/') AS
SELECT
    event_id_cnty,                 -- degenerate dimension (event id)
    iso,                           -- FK -> dim_country
    event_date,                    -- FK -> dim_date
    sub_event_type,                -- FK -> dim_event_type
    actor1,                        -- FK -> dim_actor (dim_actor.actor)
    source_scale,                  -- FK -> dim_source
    interaction,                   -- degenerate attribute
    civilian_targeting_flag,       -- additive-ish measure (0/1)
    latitude, longitude,           -- point geometry
    year,                          -- convenience (also via dim_date)
    fatalities                     -- additive measure
FROM acled_dev.gold_events_wide;
