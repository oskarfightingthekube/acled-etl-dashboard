CREATE EXTERNAL TABLE IF NOT EXISTS acled_dev.silver_events (
    country STRING,
    region STRING,
    event_type STRING,
    sub_event_type STRING,
    disorder_type STRING,
    year INT,
    event_date DATE,
    fatalities INT
)
STORED AS PARQUET
LOCATION 's3://mw-acled-silver-dev/events/';