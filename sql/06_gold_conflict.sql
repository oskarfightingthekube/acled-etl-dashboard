-- =============================================================================
-- 06_gold_conflict.sql — warstwa gold: szeroki fakt + rollupy per-pytanie
-- =============================================================================
-- ŹRÓDŁA I ROOT CAUSE (ważne, przeczytaj przed edycją):
--   * SILVER (parquet pisany Sparkiem) ma POPRAWNE fatalities (2 346 465) i
--     czyste stringi — ale glue/silver_transform.py castuje interaction/inter1/
--     inter2 do INT, a to etykiety tekstowe -> NULL w plikach silvera.
--   * BRONZE czytany przez Athena (LazySimpleSerDe) ma interaction jako string,
--     ale cudzysłowy z CSV psują kolumny LICZBOWE: BIGINT nie parsuje '"12"'
--     -> fatalities NULL w ~93% wierszy (suma 324 225 zamiast 2 346 465!).
--   * Oryginalny DDL silver_events deklaruje tylko 8 kolumn — dane w plikach
--     są kompletne, brakowało deklaracji. Stąd silver_events_full poniżej.
-- HYBRYDA: wszystko z silvera + interaction dosztukowany z bronze po
-- event_id_cnty (dedup latest-timestamp-wins jak w Glue jobie).
-- INWARIANT (weryfikowany po każdej przebudowie): count = 2 669 096,
-- sum(fatalities) = 2 346 465 w każdej tabeli tej warstwy.
-- Docelowy fix (po deadline): usunąć INT-casty w silver_transform.py,
-- re-run Glue, czytać wyłącznie z silvera.
-- =============================================================================

-- pełna deklaracja nad istniejącym parquetem silvera (dane już tam są)
CREATE EXTERNAL TABLE acled_dev.silver_events_full (
    event_id_cnty string, event_date date, year int, time_precision int,
    disorder_type string, event_type string, sub_event_type string,
    actor1 string, assoc_actor_1 string, inter1 int,
    actor2 string, assoc_actor_2 string, inter2 int, interaction int,
    civilian_targeting string, iso int, region string, country string,
    admin1 string, admin2 string, admin3 string, location string,
    latitude double, longitude double, geo_precision int,
    source string, source_scale string, notes string, fatalities int, tags string
) STORED AS PARQUET LOCATION 's3://mw-acled-silver-dev/events/';


-- -----------------------------------------------------------------------------
-- FACT TABLE — gold_events_wide
--   Grain: one row per event (deduped on event_id_cnty, latest timestamp wins,
--   deleted ids removed). Clean, typed, all reporting columns. ~2.67M rows.
--   Feeds every rollup below + the point-level / admin1 map for Q2.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_events_wide
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/events_wide/')
AS
WITH bronze_interaction AS (
    -- interaction istnieje tylko w bronze jako string; dedup identyczny jak w Glue
    SELECT event_id_cnty, trim(replace(interaction, '"', '')) AS interaction
    FROM (SELECT event_id_cnty, interaction,
                 row_number() OVER (PARTITION BY event_id_cnty ORDER BY timestamp DESC) rn
          FROM acled_dev.events)
    WHERE rn = 1
)
SELECT
    s.event_id_cnty,
    s.event_date, s.year,
    s.country, s.region, s.admin1,
    s.event_type, s.sub_event_type, s.disorder_type,
    s.actor1, s.actor2,
    b.interaction,
    CASE WHEN s.civilian_targeting = 'Civilian targeting' THEN 1 ELSE 0 END
        AS civilian_targeting_flag,
    s.latitude, s.longitude, s.iso, s.source_scale,
    s.fatalities
FROM acled_dev.silver_events_full s
LEFT JOIN bronze_interaction b ON s.event_id_cnty = b.event_id_cnty;


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
