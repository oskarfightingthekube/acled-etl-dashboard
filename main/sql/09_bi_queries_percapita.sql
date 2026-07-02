-- =============================================================================
-- 09_bi_queries_percapita.sql — Power BI reporting queries (business Q12)
-- =============================================================================
-- Source: acled_dev.gold_per_capita (built in 07_dim_population.sql). Read-only.
-- Per-capita = per 100,000 people. Filter out NULL population (Kosovo etc.) when
-- ranking by rate; keep it when showing absolute totals.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q12  Per-capita analysis — most events / fatalities per 100k, and how the
--      ranking differs from raw totals.                    ✅ full
-- -----------------------------------------------------------------------------

-- Q12a — events & fatalities per 100k for a single year (choropleth / ranked
--        bar). Change the year filter or drive it from a Power BI slicer.
SELECT
    country,
    event_count           as events,
    total_fatalities      as fatalities,
    population,
    events_per_100k,
    fatalities_per_100k
FROM acled_dev.gold_per_capita
WHERE year = 2024
  AND population IS NOT NULL
ORDER BY events_per_100k DESC;

-- Q12b — ranking flip: absolute vs per-capita, side by side (top 20 by rate).
--        Pools all years: total events / average population over the period.
WITH agg AS (
    SELECT
        country,
        SUM(event_count)      as events,
        SUM(total_fatalities) as fatalities,
        AVG(population)        as avg_population
    FROM acled_dev.gold_per_capita
    WHERE population IS NOT NULL
    GROUP BY country
)
SELECT
    country,
    events,
    fatalities,
    ROUND(events     * 100000.0 / NULLIF(avg_population, 0), 2) as events_per_100k,
    ROUND(fatalities * 100000.0 / NULLIF(avg_population, 0), 2) as fatalities_per_100k,
    RANK() OVER (ORDER BY events DESC)                                        as rank_absolute,
    RANK() OVER (ORDER BY events * 1.0 / NULLIF(avg_population, 0) DESC)      as rank_per_capita
FROM agg
ORDER BY events_per_100k DESC
LIMIT 20;

-- Q12c — per-capita trend for a chosen country over time (line chart).
SELECT
    country,
    year,
    events_per_100k,
    fatalities_per_100k
FROM acled_dev.gold_per_capita
WHERE country IN ('Ukraine', 'Palestine', 'Syria', 'Sudan')
  AND population IS NOT NULL
ORDER BY country, year;
