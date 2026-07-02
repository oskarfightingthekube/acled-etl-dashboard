# Tabela mapowań ETL — hurtownia ACLED

Opis procesów ETL w postaci tabel mapowań (źródło → transformacja → cel),
zgodnie z wymaganiami zadania. Każdy etap odpowiada zadaniu w DAG-u Airflow
`acled_pipeline` (screeny udanego ładowania każdego wymiaru i faktów — katalog
`screeny/`, widok grafu + logi zadań z Airflow UI).

Kontrola po pełnym przebiegu: **rekoncyliacja warstw** — liczba zdarzeń i suma
fatalities muszą być identyczne w silver == gold == fakt (zadanie `validate`
w DAG-u). Dane rosną przyrostowo; stan na 2.07.2026: 2 669 294 / 2 346 567.

---

## Etap 1 — Ekstrakcja: ACLED API → BRONZE (S3)

Narzędzie: Python (`src/ingest.py`), uruchamiane z `main.py`. OAuth + paginacja
po 5 000 rekordów; stan ostatniego pobrania w `state/last_run_timestamp.txt`
(ładowanie przyrostowe wg znacznika czasu — „informacja o czasie wprowadzenia
dostępna w źródle", wykład 4).

| Źródło (API) | Transformacja | Cel (S3) |
|---|---|---|
| `api/acled/read` (JSON→CSV, wszystkie pola) | brak — dane surowe as-is (warstwa append-only) | `s3://mw-acled-bronze-dev/events/{data}/page_{nnn}.csv` |
| `api/deleted/read` (identyfikatory usunięte) | brak | `s3://mw-acled-bronze-dev/deletes/{data}/page_{nnn}.csv` |

Katalogowanie: Glue Crawler → tabele `acled_dev.events`, `acled_dev.deletes`.

## Etap 2 — Przekształcenie: BRONZE → SILVER (Glue job, Spark)

Narzędzie: AWS Glue (`glue/silver_transform.py`). Wynik: Parquet,
`s3://mw-acled-silver-dev/events/` (tabela `silver_events_full`).

| Kolumna źródłowa (bronze) | Transformacja | Kolumna docelowa (silver) |
|---|---|---|
| wszystkie wiersze | **deduplikacja**: `row_number() OVER (PARTITION BY event_id_cnty ORDER BY timestamp DESC) = 1` (najnowsza wersja wygrywa — SCD typ 1) | jeden wiersz na zdarzenie |
| wszystkie wiersze | **usunięcie skasowanych**: anti-join z `deletes` po `event_id_cnty` | — |
| `event_date` (string) | CAST → `date` | `event_date` |
| `year`, `time_precision`, `iso`, `geo_precision`, `fatalities` | CAST → `int` | jw. |
| `latitude`, `longitude` | CAST → `double` | jw. |
| `inter1`, `inter2`, `interaction` | CAST → int — **znany błąd: to etykiety tekstowe → NULL** (obejście w etapie 3; docelowy fix: usunięcie castów) | jw. (NULL) |
| `timestamp` | usunięcie kolumny (techniczna) | — |
| pozostałe (actor1, country, region, source_scale, civilian_targeting, …) | bez zmian (Spark poprawnie parsuje cudzysłowy CSV) | jw. |

## Etap 3 — Integracja: SILVER + BRONZE → GOLD (Athena CTAS)

Zadanie DAG: `gold_events_wide`. Hybryda źródeł (root cause w nagłówku
`sql/06_gold_conflict.sql`): silver = poprawne liczby i czyste teksty;
bronze = jedyne źródło `interaction` jako tekst.

| Kolumna źródłowa | Źródło | Transformacja | Kolumna docelowa |
|---|---|---|---|
| `event_id_cnty`, `event_date`, `year`, `country`, `region`, `admin1`, `event_type`, `sub_event_type`, `disorder_type`, `actor1`, `actor2`, `latitude`, `longitude`, `iso`, `source_scale`, `fatalities` | silver | bez zmian | jw. |
| `civilian_targeting` | silver | `CASE WHEN = 'Civilian targeting' THEN 1 ELSE 0` (pseudo-null → 0) | `civilian_targeting_flag` |
| `interaction` | bronze | dedup jak w etapie 2 + `trim(replace(x,'"',''))` (czyszczenie cudzysłowów SerDe) | `interaction` |

## Etap 4 — Ładowanie wymiarów: GOLD → gwiazda (Athena CTAS)

Zadania DAG: `dim_country`, `dim_date`, `dim_event_type`, `dim_actor`,
`dim_source`, `dim_interaction`, `dim_population_year`. Wymiary z **kluczami
sztucznymi** `ROW_NUMBER()` + wiersz **`Unknown` (id = -1)** za pseudo-nulle
(wykład 12).

| Wymiar | Źródło | Transformacja | Klucz |
|---|---|---|---|
| `dim_country` | gold, `GROUP BY iso` | unikalne kraje + Unknown | `id_country` (surogat) |
| `dim_date` | `sequence('1997-01-01','2025-12-31')` | **ciągły kalendarz** (rok, kwartał, miesiąc, nazwa) — wymóg time-intelligence Power BI | `id_date` = yyyymmdd |
| `dim_event_type` | gold, `GROUP BY sub_event_type` | hierarchia disorder→event→sub-event + Unknown | `id_event_type` (surogat) |
| `dim_actor` | gold, `DISTINCT actor1` | + Unknown | `id_actor` (surogat) |
| `dim_source` | gold, `DISTINCT source_scale` | + Unknown | `id_source` (surogat) |
| `dim_interaction` | gold, `DISTINCT interaction` | 134 pary aktorów + Unknown (normalny wymiar — za mała liczność na zdegenerowany) | `id_interaction` (surogat) |
| `dim_population_year` | World Bank SP.POP.TOTL (`dim_population`, setup jednorazowy `sql/07`) | klucz złożony (iso, rok) spłaszczony: `iso*10000+rok` | `iso_year` |

## Etap 5 — Ładowanie faktów: GOLD + wymiary → `fact_events`

Zadanie DAG: `fact_events` (po załadowaniu wszystkich wymiarów — lookup
surogatów). Fakt zawiera **wyłącznie klucze wymiarów i miary** (Zasada 1,
wykład 3) + wymiar zdegenerowany `event_id_cnty`.

| Kolumna źródłowa (gold) | Transformacja (lookup) | Kolumna faktu |
|---|---|---|
| `iso` | JOIN `dim_country` → `COALESCE(id, -1)` | `id_country` |
| `event_date` | `yyyymmdd` (formuła, bez joinu) | `id_date` |
| `sub_event_type` | JOIN `dim_event_type` → `COALESCE(id, -1)` | `id_event_type` |
| `actor1` | JOIN `dim_actor` → `COALESCE(id, -1)` | `id_actor` |
| `source_scale` | JOIN `dim_source` → `COALESCE(id, -1)` | `id_source` |
| `interaction` | JOIN `dim_interaction` → `COALESCE(id, -1)` | `id_interaction` |
| `iso`, `year` | `iso*10000+year` (klucz populacji) | `iso_year` |
| `fatalities` | bez zmian — **miara addytywna** | `fatalities` |
| `civilian_targeting_flag` | bez zmian — **miara 0/1 (addytywna)** | `civilian_targeting_flag` |
| `event_id_cnty` | bez zmian — wymiar zdegenerowany | `event_id_cnty` |

## Etap 6 — Walidacja (zadanie `validate` w DAG-u)

| Kontrola | Oczekiwane | Jak |
|---|---|---|
| zgodność liczby zdarzeń | silver == gold == fakt | rekoncyliacja — assert w DAG-u |
| zgodność sumy fatalities | silver == gold == fakt | rekoncyliacja — assert w DAG-u |
| integralność FK (sieroty) | 0 dla każdego wymiaru | LEFT JOIN fakt→wymiar, `COUNT(id IS NULL)` |
| unikalność surogatów | rows = distinct w każdym wymiarze | `COUNT(*) vs COUNT(DISTINCT id)` |
