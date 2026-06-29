CREATE TABLE acled_dev.gold_geography
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/geography/')
AS
SELECT
    country,
    region,
    event_type,
    COUNT(*) as event_count,
    SUM(fatalities) as total_fatalities,
    ROUND(AVG(CAST(fatalities AS DOUBLE)), 2) as avg_fatalities
FROM acled_dev.silver_events
GROUP BY country, region, event_type
ORDER BY event_count DESC;