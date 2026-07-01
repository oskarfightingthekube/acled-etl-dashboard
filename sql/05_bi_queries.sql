-- =============================================================================
-- 05_bi_queries.sql — Power BI reporting queries (business questions 1–5)
-- =============================================================================
-- Source: the 3 gold rollup tables built by 02/03/04. Read-only; nothing here
-- modifies a table. Run against Athena database `acled_dev`.
--
-- Two ways to use these in Power BI:
--   A) Import the whole gold table (Get Data > Amazon Athena) and reproduce the
--      GROUP BY inside the visual's own field wells. Best for slice/drill.
--   B) Paste a query below as a Power BI "native query" for a fixed result set.
-- Each block is labelled with the question + the visual it feeds. Coverage
-- notes (✅ full / ⚠️ partial) match docs/powerbi_design_spec.md.
--
-- VERIFIED against acled_dev (eu-central-1): every query returns rows; the two
-- gold tables cross-check (SUM(event_count) = 2,669,096 in both). Data spans
-- 1997–2025. All Q5c sub_event_type values below confirmed present.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1  Geography & Scale — which countries/regions have the most events, and
--     which event types are most common there.            ✅ full
-- -----------------------------------------------------------------------------

-- Q1a — top countries by events + fatalities (ranked bar / table).
SELECT
    country,
    region,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_geography
GROUP BY country, region
ORDER BY events DESC;

-- Q1b — top regions by events (ranked bar).
SELECT
    region,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_geography
GROUP BY region
ORDER BY events DESC;

-- Q1c — event-type mix per country (feeds a drill-down matrix / stacked bar).
--       Import gold_geography as-is for this; the table grain already is
--       country × region × event_type.
SELECT
    country,
    region,
    event_type,
    event_count,
    total_fatalities
FROM acled_dev.gold_geography
ORDER BY country, event_count DESC;


-- -----------------------------------------------------------------------------
-- Q2  Deaths map + deadliest places per event.            ⚠️ partial
--     gold has no lat/long → map is a country choropleth / bubble-by-country
--     (Power BI built-in geocoding), not point-level.
-- -----------------------------------------------------------------------------

-- Q2a — fatalities by country for the map + fatalities-per-event intensity.
SELECT
    country,
    region,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities,
    ROUND(SUM(total_fatalities) * 1.0 / NULLIF(SUM(event_count), 0), 2)
                          as fatalities_per_event
FROM acled_dev.gold_geography
GROUP BY country, region
ORDER BY fatalities DESC;

-- Q2b — highest fatalities-per-event places (deadliest-per-incident ranking).
--       min 50 events to drop tiny-sample outliers; tune as needed.
SELECT
    country,
    region,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities,
    ROUND(SUM(total_fatalities) * 1.0 / NULLIF(SUM(event_count), 0), 2)
                          as fatalities_per_event
FROM acled_dev.gold_geography
GROUP BY country, region
HAVING SUM(event_count) >= 50
ORDER BY fatalities_per_event DESC;


-- -----------------------------------------------------------------------------
-- Q3  Time trends — events over time by disorder_type.    ✅ full
-- -----------------------------------------------------------------------------

-- Q3a — yearly trend per disorder_type (multi-line chart, legend = disorder_type).
SELECT
    year,
    disorder_type,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_yearly_trends
GROUP BY year, disorder_type
ORDER BY year, disorder_type;

-- Q3b — monthly trend per disorder_type (year+month axis for finer granularity).
SELECT
    year,
    month,
    disorder_type,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_yearly_trends
GROUP BY year, month, disorder_type
ORDER BY year, month, disorder_type;


-- -----------------------------------------------------------------------------
-- Q4  Seasonality — which months have the most events / fatalities.  ✅ full
-- -----------------------------------------------------------------------------

-- Q4a — events + fatalities by calendar month, all years combined (column chart).
SELECT
    month,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_yearly_trends
GROUP BY month
ORDER BY month;

-- Q4b — month × year heatmap (matrix: rows = month, cols = year, value = events).
SELECT
    month,
    year,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_yearly_trends
GROUP BY month, year
ORDER BY month, year;


-- -----------------------------------------------------------------------------
-- Q5  Event types — deadliest event/sub_event + avg fatalities per event.
--                                                          ⚠️ partial
--     "deadliest + avg" is fully answerable. The protest-vs-violence ratio
--     OVER TIME is NOT — gold_event_types has no time dimension and
--     gold_yearly_trends carries no event_type. A static ratio is provided;
--     the over-time version needs a new gold table (event_type × year).
-- -----------------------------------------------------------------------------

-- Q5a — deadliest event/sub_event types (bar by total_fatalities + avg label).
SELECT
    event_type,
    sub_event_type,
    event_count,
    total_fatalities,
    avg_fatalities_per_event
FROM acled_dev.gold_event_types
ORDER BY total_fatalities DESC;

-- Q5b — avg fatalities per event, ranked (which incident types are deadliest
--       per occurrence, independent of volume).
SELECT
    event_type,
    sub_event_type,
    event_count,
    avg_fatalities_per_event
FROM acled_dev.gold_event_types
WHERE event_count >= 50          -- drop tiny-sample outliers; tune as needed
ORDER BY avg_fatalities_per_event DESC;

-- Q5c — static protest-vs-violence ratio (single KPI card).
--       Peaceful protests vs the violent-demonstration sub-types. All four
--       sub_event_type values below verified present in the data (Peaceful
--       protest = 1,033,397 events; violent set = 130,426 combined).
SELECT
    SUM(CASE WHEN sub_event_type = 'Peaceful protest'
             THEN event_count ELSE 0 END) as peaceful_protests,
    SUM(CASE WHEN sub_event_type IN ('Violent demonstration',
                                     'Protest with intervention',
                                     'Excessive force against protesters')
             THEN event_count ELSE 0 END) as violent_demonstrations,
    ROUND(
        SUM(CASE WHEN sub_event_type = 'Peaceful protest'
                 THEN event_count ELSE 0 END) * 1.0
        / NULLIF(SUM(CASE WHEN sub_event_type IN ('Violent demonstration',
                                                  'Protest with intervention',
                                                  'Excessive force against protesters')
                          THEN event_count ELSE 0 END), 0), 2
    ) as peaceful_to_violent_ratio
FROM acled_dev.gold_event_types;
