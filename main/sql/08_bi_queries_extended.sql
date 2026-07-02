-- =============================================================================
-- 08_bi_queries_extended.sql — Power BI reporting queries (business Q6–11)
-- =============================================================================
-- Sources: the extended gold tables from 06_gold_conflict.sql. Read-only.
-- Run against Athena database `acled_dev`. Coverage notes: ✅ full / ⚠️ partial.
-- Per-capita (Q12) lives in 09_bi_queries_percapita.sql (needs dim_population).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q6  Actors.                                              ✅ full
-- -----------------------------------------------------------------------------

-- Q6a — top actors by events + deaths (ranked bar / table).
SELECT
    actor1,
    SUM(event_count)            as events,
    SUM(total_fatalities)       as fatalities,
    SUM(civ_targeting_events)   as civ_events
FROM acled_dev.gold_actors
GROUP BY actor1
ORDER BY events DESC
LIMIT 25;

-- Q6b — actor activity over time (line chart; import full table, filter to the
--       top actors in the visual, plot year on axis / actor1 on legend).
SELECT
    actor1,
    year,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_actors
GROUP BY actor1, year
ORDER BY year, events DESC;

-- Q6c — interaction types most common + bloodiest (bar; sort by fatalities,
--       fatalities_per_event as the intensity label).
SELECT
    interaction,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities,
    ROUND(SUM(total_fatalities) * 1.0 / NULLIF(SUM(event_count), 0), 2)
                          as fatalities_per_event
FROM acled_dev.gold_interaction
GROUP BY interaction
ORDER BY fatalities DESC;


-- -----------------------------------------------------------------------------
-- Q7  Civilian targeting.                                  ✅ full
-- -----------------------------------------------------------------------------

-- Q7a — % of events that are civilian-targeting, by region.
SELECT
    region,
    SUM(event_count)            as events,
    SUM(civ_targeting_events)   as civ_events,
    ROUND(SUM(civ_targeting_events) * 100.0 / NULLIF(SUM(event_count), 0), 1)
                                as pct_civilian_targeting
FROM acled_dev.gold_civilian_region
GROUP BY region
ORDER BY pct_civilian_targeting DESC;

-- Q7b — civilian-targeting % over time, by region (line, legend = region).
SELECT
    year,
    region,
    ROUND(SUM(civ_targeting_events) * 100.0 / NULLIF(SUM(event_count), 0), 1)
                                as pct_civilian_targeting
FROM acled_dev.gold_civilian_region
GROUP BY year, region
ORDER BY year, region;

-- Q7c — civilian-targeting rate by actor (which actors target civilians most).
--       min 200 events to drop tiny-sample outliers.
SELECT
    actor1,
    SUM(event_count)            as events,
    SUM(civ_targeting_events)   as civ_events,
    ROUND(SUM(civ_targeting_events) * 100.0 / NULLIF(SUM(event_count), 0), 1)
                                as pct_civilian_targeting
FROM acled_dev.gold_actors
GROUP BY actor1
HAVING SUM(event_count) >= 200
ORDER BY pct_civilian_targeting DESC
LIMIT 25;


-- -----------------------------------------------------------------------------
-- Q8  Sources & precision.                                 ⚠️ partial
--     source_scale (local/national/international) by region is fully answerable.
--     The "do more sources mean more reported events?" sub-question is NOT —
--     it needs a count of distinct sources per event (the raw `source` list),
--     which the gold layer doesn't carry. Would require adding a source-count
--     column to gold_events_wide (e.g. cardinality(split(source, ';'))).
-- -----------------------------------------------------------------------------

-- Q8a — source_scale mix by region (stacked bar; local vs national vs intl).
SELECT
    region,
    source_scale,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_sources
GROUP BY region, source_scale
ORDER BY region, events DESC;

-- Q8b — overall source_scale distribution (donut / bar).
SELECT
    source_scale,
    SUM(event_count) as events
FROM acled_dev.gold_sources
GROUP BY source_scale
ORDER BY events DESC;


-- -----------------------------------------------------------------------------
-- Q9  Escalation.                                          ✅ full
-- -----------------------------------------------------------------------------

-- Q9a — biggest year-over-year increase in events, per country (LAG window).
WITH y AS (
    SELECT country, year,
           SUM(event_count)      as events,
           SUM(total_fatalities) as fatalities
    FROM acled_dev.gold_country_year
    GROUP BY country, year
)
SELECT
    country,
    year,
    events,
    events - LAG(events) OVER (PARTITION BY country ORDER BY year) as yoy_change,
    ROUND((events - LAG(events) OVER (PARTITION BY country ORDER BY year)) * 100.0
          / NULLIF(LAG(events) OVER (PARTITION BY country ORDER BY year), 0), 1)
                                                                   as yoy_pct
FROM y
ORDER BY yoy_change DESC
LIMIT 25;

-- Q9b — "does more events always mean more fatalities?" (scatter: one point per
--       country-year, x = events, y = fatalities; add a trend line in the visual).
SELECT
    country,
    year,
    SUM(event_count)      as events,
    SUM(total_fatalities) as fatalities
FROM acled_dev.gold_country_year
GROUP BY country, year
ORDER BY events DESC;
