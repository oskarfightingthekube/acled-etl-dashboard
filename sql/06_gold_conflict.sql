-- =============================================================================
-- 06_gold_conflict.sql — extended gold layer for business questions 6–11
--   (actors, interaction, civilian targeting, sources, escalation) + a clean
--   event-level fact table that also enables a point/admin1 map for Q2 and the
--   protest-vs-violence-over-time answer for Q5.
-- =============================================================================
-- WHY THIS EXISTS (read before editing):
--   The 3 original gold tables (02–04) only cover Q1–5. The columns needed for
--   Q6–11 (actor1, interaction, civilian_targeting, source_scale, lat/long)
--   live in the raw `events` table but were NOT surfaced by the silver layer:
--     * silver_events' Athena DDL declares only 8 columns, and
--     * glue/silver_transform.py CASTs `interaction`/`inter1`/`inter2` to INT —
--       but in this dataset they are STRING labels ("State forces-Rebel group"),
--       so the cast yields NULL. silver's interaction is therefore unusable.
--   So this file rebuilds a clean fact table straight from `events`, applying
--   the SAME dedup + delete logic as silver (validated: identical 2,669,096
--   row count), and fixes two raw-data problems Athena's CSV SerDe leaves behind:
--     1. literal double-quotes wrapping most string values  -> trim(replace(x,'"',''))
--     2. civilian_targeting stored as '"Civilian targeting"' -> flag via replace()
--   All tables VERIFIED in acled_dev (eu-central-1): every rollup's
--   SUM(event_count) = 2,669,096, matching the original gold layer.
--
-- KNOWN MINOR ARTIFACT: a handful of misaligned source rows carry a bad value
--   in `fatalities`, producing tiny negative sums for a few actors (net ~-20
--   over 79k events). Negligible vs real totals; clamp with GREATEST(x,0) if a
--   stakeholder objects.
--
-- Run order: this whole file (fact table first, then the six rollups).
-- Output location for Athena results: s3://mw-acled-gold-dev/athena-results/
-- =============================================================================


-- -----------------------------------------------------------------------------
-- FACT TABLE — gold_events_wide
--   Grain: one row per event (deduped on event_id_cnty, latest timestamp wins,
--   deleted ids removed). Clean, typed, all reporting columns. ~2.67M rows.
--   Feeds every rollup below + the point-level / admin1 map for Q2.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_events_wide
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/events_wide/')
AS
WITH deduped AS (
    SELECT *,
           row_number() OVER (PARTITION BY event_id_cnty ORDER BY timestamp DESC) rn
    FROM acled_dev.events
),
clean AS (
    SELECT d.* FROM deduped d
    LEFT JOIN (SELECT DISTINCT event_id_cnty FROM acled_dev.deletes) del
        ON d.event_id_cnty = del.event_id_cnty
    WHERE d.rn = 1 AND del.event_id_cnty IS NULL
)
SELECT
    event_id_cnty,
    CAST(event_date AS date)                         AS event_date,
    CAST(year AS int)                                AS year,
    trim(replace(country,        '"', ''))           AS country,
    trim(replace(region,         '"', ''))           AS region,
    trim(replace(admin1,         '"', ''))           AS admin1,
    trim(replace(event_type,     '"', ''))           AS event_type,
    trim(replace(sub_event_type, '"', ''))           AS sub_event_type,
    trim(replace(disorder_type,  '"', ''))           AS disorder_type,
    trim(replace(actor1,         '"', ''))           AS actor1,
    trim(replace(actor2,         '"', ''))           AS actor2,
    trim(replace(interaction,    '"', ''))           AS interaction,
    CASE WHEN replace(civilian_targeting, '"', '') = 'Civilian targeting'
         THEN 1 ELSE 0 END                           AS civilian_targeting_flag,
    latitude,
    longitude,
    CAST(iso AS int)                                 AS iso,
    trim(replace(source_scale,   '"', ''))           AS source_scale,
    CAST(fatalities AS int)                          AS fatalities
FROM clean;


-- -----------------------------------------------------------------------------
-- Q6  Actors — actor1 activity + deaths over time, and civilian targeting by
--     actor (civ_targeting_events also feeds Q7).   Grain: actor1 × year.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_actors
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/actors/')
AS
SELECT
    actor1,
    year,
    COUNT(*)                        as event_count,
    SUM(fatalities)                 as total_fatalities,
    SUM(civilian_targeting_flag)    as civ_targeting_events
FROM acled_dev.gold_events_wide
GROUP BY actor1, year;


-- -----------------------------------------------------------------------------
-- Q6  Interaction types — which actor-pairings happen most and are bloodiest.
--     Grain: interaction × year.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_interaction
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/interaction/')
AS
SELECT
    interaction,
    year,
    COUNT(*)            as event_count,
    SUM(fatalities)     as total_fatalities
FROM acled_dev.gold_events_wide
GROUP BY interaction, year;


-- -----------------------------------------------------------------------------
-- Q7  Civilian targeting by region, over time. % = civ / events.
--     Grain: region × year.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_civilian_region
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/civilian_region/')
AS
SELECT
    region,
    year,
    COUNT(*)                        as event_count,
    SUM(civilian_targeting_flag)    as civ_targeting_events,
    SUM(fatalities)                 as total_fatalities
FROM acled_dev.gold_events_wide
GROUP BY region, year;


-- -----------------------------------------------------------------------------
-- Q8  Sources & precision — source_scale (local vs international) by region.
--     Grain: region × source_scale.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_sources
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/sources/')
AS
SELECT
    region,
    source_scale,
    COUNT(*)            as event_count,
    SUM(fatalities)     as total_fatalities
FROM acled_dev.gold_events_wide
GROUP BY region, source_scale;


-- -----------------------------------------------------------------------------
-- Q9  Escalation — country × year totals. YoY change is computed in the BI
--     query with LAG (see 08_bi_queries_extended.sql). `iso` is kept so this
--     joins to dim_population for per-capita (Q12).  Grain: country × iso × year.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_country_year
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/country_year/')
AS
SELECT
    country,
    iso,
    year,
    COUNT(*)            as event_count,
    SUM(fatalities)     as total_fatalities
FROM acled_dev.gold_events_wide
GROUP BY country, iso, year;


-- -----------------------------------------------------------------------------
-- Q5 (over time) — event_type / disorder_type per year. Fixes the earlier gap:
--     protest-vs-violence RATIO over time is now answerable.
--     Grain: event_type × disorder_type × year.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_event_type_year
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/event_type_year/')
AS
SELECT
    event_type,
    disorder_type,
    year,
    COUNT(*)            as event_count,
    SUM(fatalities)     as total_fatalities
FROM acled_dev.gold_events_wide
GROUP BY event_type, disorder_type, year;
