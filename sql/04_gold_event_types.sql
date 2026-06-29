CREATE TABLE acled_dev.gold_event_types
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/event_types/')
AS
SELECT
    event_type,
    sub_event_type,
    COUNT(*) as event_count,
    SUM(fatalities) as total_fatalities,
    ROUND(AVG(CAST(fatalities AS DOUBLE)), 2) as avg_fatalities_per_event
FROM acled_dev.silver_events
GROUP BY event_type, sub_event_type
ORDER BY total_fatalities DESC;