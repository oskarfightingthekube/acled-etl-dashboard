-- =============================================================================
-- 10_star_schema.sql — CZYSTY schemat gwiazdy (hurtownia jednotematyczna)
-- =============================================================================
-- Temat hurtowni: zdarzenia konfliktów zbrojnych (ACLED).
-- Ziarnistość:    jedno zdarzenie (fakt transakcyjny).
-- Miary:          fatalities (addytywna), civilian_targeting_flag (0/1, addytywna).
-- Wymiary:        kraj, data, typ zdarzenia, aktor, źródło, interakcja, populacja.
--
-- Zgodność z zasadami z wykładu 3:
--   * Zasada 1 — w tabeli faktów TYLKO miary i klucze wymiarów. Jedyny wyjątek:
--     event_id_cnty jako wymiar zdegenerowany (unikalny per wiersz faktu,
--     analogia do „NrZamówienia" z wykładu).
--   * Zasada 2 — 7 wymiarów (< 25).
--   * Zasada 3 — fakt (2 669 096) istotnie największy (największy wymiar: 16,5 tys.).
--   * Wymiary z kluczami sztucznymi (surogatami) id_* — jak w schematach
--     z wykładu (IdProduktu, IdKlienta, IdCzasu). Klucz daty = yyyymmdd (INT).
--   * interaction jest NORMALNYM wymiarem (134 wartości — za mała liczność na
--     wymiar zdegenerowany wg definicji z wykładu).
--   * Pseudo-NULL-e w wymiarach zamienione na wiersz „Unknown" (id = -1),
--     zgodnie z zasadami jakości danych (wykład 12).
--
-- Źródło: acled_dev.gold_events_wide (oczyszczony, zdeduplikowany fakt szeroki
-- z 06_gold_conflict.sql). Kolumny odrzucone z faktu (lat/long, year, surowe
-- etykiety) pozostają dostępne w gold_events_wide.
--
-- Power BI relationships (wszystkie *:1, wymiar po stronie 1):
--   fact_events[id_country]     -> dim_country[id_country]
--   fact_events[id_date]        -> dim_date[id_date]
--   fact_events[id_event_type]  -> dim_event_type[id_event_type]
--   fact_events[id_actor]       -> dim_actor[id_actor]
--   fact_events[id_source]      -> dim_source[id_source]
--   fact_events[id_interaction] -> dim_interaction[id_interaction]
--   fact_events[iso_year]       -> dim_population_year[iso_year]
-- =============================================================================

-- --- wymiary (surogaty ROW_NUMBER po unikalnym kluczu naturalnym + wiersz Unknown) ---

CREATE TABLE acled_dev.dim_country
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_country/') AS
SELECT ROW_NUMBER() OVER (ORDER BY iso) as id_country, iso, country, region
FROM (SELECT iso, arbitrary(country) country, arbitrary(region) region
      FROM acled_dev.gold_events_wide WHERE iso IS NOT NULL GROUP BY iso)
UNION ALL SELECT -1, NULL, 'Unknown', 'Unknown';

-- ciągły kalendarz (wymóg Power BI: Mark as date table, DATEADD/YoY);
-- klucz sztuczny yyyymmdd — standardowy "smart key" wymiaru czasu
CREATE TABLE acled_dev.dim_date
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_date/') AS
SELECT CAST(date_format(d,'%Y%m%d') AS int) as id_date,
       CAST(d AS date)             as date_key,
       year(d)                     as year,
       quarter(d)                  as quarter,
       month(d)                    as month,
       date_format(d,'%M')         as month_name
FROM UNNEST(sequence(date '1997-01-01', date '2025-12-31', interval '1' day)) AS t(d);

CREATE TABLE acled_dev.dim_event_type
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_event_type/') AS
SELECT ROW_NUMBER() OVER (ORDER BY sub_event_type) as id_event_type,
       sub_event_type, event_type, disorder_type
FROM (SELECT sub_event_type, arbitrary(event_type) event_type,
             arbitrary(disorder_type) disorder_type
      FROM acled_dev.gold_events_wide WHERE sub_event_type IS NOT NULL
      GROUP BY sub_event_type)
UNION ALL SELECT -1, 'Unknown', 'Unknown', 'Unknown';

CREATE TABLE acled_dev.dim_actor
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_actor/') AS
SELECT ROW_NUMBER() OVER (ORDER BY actor) as id_actor, actor
FROM (SELECT DISTINCT actor1 as actor FROM acled_dev.gold_events_wide
      WHERE actor1 IS NOT NULL)
UNION ALL SELECT -1, 'Unknown';

CREATE TABLE acled_dev.dim_source
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_source/') AS
SELECT ROW_NUMBER() OVER (ORDER BY source_scale) as id_source, source_scale
FROM (SELECT DISTINCT source_scale FROM acled_dev.gold_events_wide
      WHERE source_scale IS NOT NULL)
UNION ALL SELECT -1, 'Unknown';

CREATE TABLE acled_dev.dim_interaction
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_interaction/') AS
SELECT ROW_NUMBER() OVER (ORDER BY interaction) as id_interaction, interaction
FROM (SELECT DISTINCT interaction FROM acled_dev.gold_events_wide
      WHERE interaction IS NOT NULL)
UNION ALL SELECT -1, 'Unknown';

-- populacja: klucz złożony (iso, rok) spłaszczony do iso_year (relacje PBI
-- są 1-kolumnowe); zależy od dim_population (07_dim_population.sql)
CREATE TABLE acled_dev.dim_population_year
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/dim_population_year/') AS
SELECT iso_numeric * 10000 + year as iso_year,
       iso_numeric as iso, year, country_name, population
FROM acled_dev.dim_population;

-- --- fakt: TYLKO klucze wymiarów + miary (+ degenerate event_id_cnty) ---

CREATE TABLE acled_dev.fact_events
WITH (format='PARQUET', external_location='s3://mw-acled-gold-dev/star/fact_events/') AS
SELECT
    w.event_id_cnty,                                        -- wymiar zdegenerowany
    COALESCE(c.id_country, -1)                as id_country,
    CAST(date_format(w.event_date,'%Y%m%d') AS int)
                                              as id_date,
    COALESCE(e.id_event_type, -1)             as id_event_type,
    COALESCE(a.id_actor, -1)                  as id_actor,
    COALESCE(s.id_source, -1)                 as id_source,
    COALESCE(i.id_interaction, -1)            as id_interaction,
    CASE WHEN w.iso IS NOT NULL THEN w.iso * 10000 + w.year END
                                              as iso_year,  -- FK -> dim_population_year
    w.fatalities,                                            -- miara addytywna
    w.civilian_targeting_flag                                -- miara 0/1 (addytywna)
FROM acled_dev.gold_events_wide w
LEFT JOIN acled_dev.dim_country     c ON w.iso            = c.iso
LEFT JOIN acled_dev.dim_event_type  e ON w.sub_event_type = e.sub_event_type
LEFT JOIN acled_dev.dim_actor       a ON w.actor1         = a.actor
LEFT JOIN acled_dev.dim_source      s ON w.source_scale   = s.source_scale
LEFT JOIN acled_dev.dim_interaction i ON w.interaction    = i.interaction;
