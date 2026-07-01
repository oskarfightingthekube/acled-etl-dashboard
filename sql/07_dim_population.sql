-- =============================================================================
-- 07_dim_population.sql — population dimension + per-capita gold (Q12)
-- =============================================================================
-- dim_population is external over a tab-separated file in S3 (World Bank
-- indicator SP.POP.TOTL, total population, 215 countries × 1997–2025).
-- Data file: s3://mw-acled-gold-dev/dim_population/dim_population.tsv (no header).
--
-- WHY TSV + LazySimpleSerDe (not CSV/OpenCSVSerde): World Bank country names
-- contain commas ("Korea, Rep."), and OpenCSVSerde forces every column to
-- STRING — which would break the INT/BIGINT typing needed for the numeric join.
-- Tabs never occur in the data, so tab-delimited keeps the numeric types honest.
--
-- JOIN KEY: dim_population.iso_numeric is the ISO 3166-1 NUMERIC code, identical
-- to ACLED's `iso` (Afghanistan=4, Ukraine=804), so it joins directly with no
-- casting: gold_country_year.iso = dim_population.iso_numeric AND ...year = year.
--
-- COVERAGE: ~99.35% of events match a population row. Unmatched (~17.4k events)
-- is almost entirely Kosovo — ISO 3166-1 assigns it no numeric code, so it has
-- no World Bank population row to join. per-capita is NULL for those (LEFT JOIN
-- keeps them visible in absolute terms).
-- =============================================================================

CREATE EXTERNAL TABLE acled_dev.dim_population (
    iso_numeric  INT,
    iso3         STRING,
    country_name STRING,
    year         INT,
    population   BIGINT
)
ROW FORMAT DELIMITED
    FIELDS TERMINATED BY '\t'
    LINES TERMINATED BY '\n'
STORED AS TEXTFILE
LOCATION 's3://mw-acled-gold-dev/dim_population/'
TBLPROPERTIES ('has_encrypted_data' = 'false');


-- -----------------------------------------------------------------------------
-- gold_per_capita — country × year events/fatalities normalised per 100k people.
--   Grain: country × iso × year. LEFT JOIN keeps countries without a population
--   match (per-capita cols NULL for them). Feeds Q12.
-- -----------------------------------------------------------------------------
CREATE TABLE acled_dev.gold_per_capita
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/per_capita/')
AS
SELECT
    c.country,
    c.iso,
    c.year,
    c.event_count,
    c.total_fatalities,
    p.population,
    ROUND(c.event_count      * 100000.0 / NULLIF(p.population, 0), 2) as events_per_100k,
    ROUND(c.total_fatalities * 100000.0 / NULLIF(p.population, 0), 2) as fatalities_per_100k
FROM acled_dev.gold_country_year c
LEFT JOIN acled_dev.dim_population p
    ON c.iso = p.iso_numeric AND c.year = p.year;
