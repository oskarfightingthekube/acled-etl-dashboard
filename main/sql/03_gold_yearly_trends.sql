CREATE TABLE acled_dev.gold_yearly_trends
WITH (format = 'PARQUET', external_location = 's3://mw-acled-gold-dev/yearly_trends/')
AS
SELECT
    year,
    MONTH(event_date) as month,
    disorder_type,
    COUNT(*) as event_count,
    SUM(fatalities) as total_fatalities
FROM acled_dev.silver_events
GROUP BY year, MONTH(event_date), disorder_type
ORDER BY year, month;