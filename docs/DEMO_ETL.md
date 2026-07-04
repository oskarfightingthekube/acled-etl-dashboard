# Demo ETL na żywo — ściąga prezentera

Cel pokazu: udowodnić, że pipeline działa naprawdę — **stan przed → uruchomienie
ETL → stan po** (przybyły najnowsze zdarzenia). Wszystko odwracalne skryptem
`demo/etl_demo.sh` (revert/restore), więc pokaz można powtórzyć dowolną liczbę razy.

---

## 1. Co dokładnie robi nasz ETL (do opowiedzenia przy grafie)

**DAG 1 — `acled_manual_backfill`** (ekstrakcja; wymaga konta ACLED):
| Zadanie | Co robi |
|---|---|
| `event_load` / `delete_load` | logowanie OAuth do API ACLED; pobór **przyrostowy**: tylko rekordy ze znacznikiem czasu nowszym niż zapamiętany w `state/last_run_timestamp.txt` na S3; zapis surowych CSV do bronze (`events/RRRR-MM-DD/page_NNN.csv`) — warstwa append-only |
| `check_new_data` | **ShortCircuit** — jeśli nic nowego, dalsze kroki się nie wykonują |
| `run_bronze_crawler_*` | Glue Crawler aktualizuje katalog (metadane techniczne) |
| `silver_transform` | job Spark: **deduplikacja** po `event_id_cnty` (najnowszy timestamp wygrywa = SCD typ 1), usunięcie rekordów z rejestru `deletes`, typowanie, zapis Parquet |

**DAG 2 — `acled_pipeline`** (transformacja + ładowanie + walidacja):
| Zadanie | Co robi |
|---|---|
| `crawl_bronze`, `silver_transform` | (opcjonalne, param `run_glue`) — jak wyżej |
| `gold_events_wide` | Athena CTAS: integracja silver+bronze, flaga celowania w cywilów, czyszczenie pseudo-nulli |
| `dim_*` (7 zadań) | wymiary gwiazdy: klucze sztuczne ROW_NUMBER + wiersz Unknown(−1); `dim_date` = ciągły kalendarz |
| `fact_events` | fakt: lookup surogatów (LEFT JOIN + COALESCE −1), tylko klucze i miary |
| `validate` | **rekoncyliacja warstw**: liczba zdarzeń ORAZ suma ofiar muszą być identyczne w silver == gold == fakt; różnica = czerwony task |

Cechy do podkreślenia: **idempotencja** (każdy CTAS: DROP + czyszczenie S3 + CREATE —
DAG można puszczać wielokrotnie), **przyrostowość** (znacznik czasu w state),
**automatyczna walidacja** po każdym runie.

---

## 2. Scenariusz pokazu (10–15 min)

### Przygotowanie (rano, przed zajęciami)
```bash
cd ~/Desktop/acled-etl-dashboard
open -a OrbStack                               # Docker musi żyć
(cd airflow && docker compose up -d)           # Airflow wstaje
DZIEN=2026-07-04 demo/etl_demo.sh przygotuj    # revert dzisiejszej paczki + trigger pipeline
# czekasz ~8 min na zielono (run_glue=TRUE ustawia się samo)
demo/etl_demo.sh status                        # potwierdzasz: 2 669 096, najnowsza data 2025-06-29
python3 demo/pokaz.py                          # licznik DOPIERO TERAZ (łapie baseline "wczorajszy")
```
Od tego momentu system jest „cofnięty" i gotowy do pokazu.
Hasło do Airflow UI (regeneruje się przy odtworzeniu kontenera):
`cd airflow && docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated`
Konto ACLED: `airflow/.env` — działa, przetestowane 4.07.

### Na żywo przy prowadzącej (wersja z licznikiem — polecana)
0. Terminal na pełnym ekranie (rzutnik): `python3 demo/pokaz.py`
   → wielki licznik zdarzeń (stan bazowy) + lista najświeższych zdarzeń;
   odświeża się sam co 20 s. Zostawiasz włączony przez cały pokaz.
1. **Stan PRZED** — widoczny na liczniku (alternatywnie tekstowo:
   `demo/etl_demo.sh status`).
2. **Ingest** (wybierz wariant):
   - **A. Live z API — GŁÓWNY (przetestowany 4.07)**: Airflow UI →
     `acled_manual_backfill` → Trigger (full=false). W logach `event_load` widać
     pobór stron z API na żywo (~30 stron, bo lecą też korekty wsteczne — patrz
     pytania niżej). Potem crawlery + silver (~6–8 min łącznie). Po zielonym:
     `acled_pipeline` → Trigger z **run_glue=FALSE** (silver już świeży) — ~1 min.
   - **B. Fallback bez API**: `DZIEN=2026-07-04 demo/etl_demo.sh restore` —
     „symulacja dostarczenia paczki przez źródło". Potem Airflow UI →
     `acled_pipeline` → **Trigger z run_glue=TRUE** (~8 min).
3. W trakcie czekania: pokaż graf DAG-a, klikaj taski → logi; opowiedz walidację.
4. **Stan PO** — licznik sam skacze po zakończeniu DAG-a: zielony pasek
   „▲ +323 NOWYCH ZDARZEŃ OD STARTU DEMA", najnowsza data przeskakuje
   z 2025-06-29 na 2025-07-04 (wariant A; przy B: +198 i 2025-07-02), w tabeli
   świeże zdarzenia (Jemen/USA). `validate` zielony = warstwy spójne.
   (Tekstowo: `demo/etl_demo.sh status`.)
5. Puenta: „pipeline jest idempotentny i zwalidowany — możemy to powtórzyć od ręki"
   (i faktycznie możesz: revert → run → restore → run).

### Awaryjnie / powtórka
```bash
demo/etl_demo.sh revert     # znowu cofa (przyrost do backupu + znacznik -3 dni)
# Trigger acled_pipeline (run_glue=TRUE) -> stan sprzed
demo/etl_demo.sh restore    # i z powrotem
```
Skrypt NICZEGO nie kasuje na twardo — wszystko ląduje w `demo-backup/` na S3.

---

## 3. Komendy pomocnicze (gdyby pytała głębiej)

```bash
# znacznik przyrostu (unix ts):
aws s3 cp s3://mw-acled-bronze-dev/state/last_run_timestamp.txt -

# surowe pliki bronze z konkretnego dnia:
aws s3 ls s3://mw-acled-bronze-dev/events/2026-07-02/

# hasło do Airflow (Airflow 3, standalone):
cd airflow && docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Zapytania Athena (konsola AWS albo skrypt status):
```sql
-- rekoncyliacja (to samo liczy task validate):
SELECT 'silver' w, count(*), sum(fatalities) FROM acled_dev.silver_events_full
UNION ALL SELECT 'gold', count(*), sum(fatalities) FROM acled_dev.gold_events_wide
UNION ALL SELECT 'fact', count(*), sum(fatalities) FROM acled_dev.fact_events;
```

---

## 4. Pytania, które mogą paść przy demie

- **„Czemu najnowsze zdarzenia są sprzed roku?"** — źródło (ACLED) publikuje dane
  z 12-miesięcznym embargiem dla naszego poziomu dostępu; opóźnienie znane z góry
  (dokładnie tak, jak definicja OLAP z wykładu 1 dopuszcza). Pipeline dociąga
  codziennie „dziś minus rok" + korekty wsteczne.
- **„Skąd wiadomo, że dane się nie zepsuły?"** — task `validate`: rekoncyliacja
  liczby zdarzeń i sumy ofiar między warstwami po każdym runie; przy rozjeździe
  DAG robi się czerwony.
- **„Co jak uruchomię drugi raz?"** — idempotencja: DROP + czyszczenie prefixu +
  CTAS; wynik identyczny, żadnych duplikatów.
- **„Czemu pobiera ~30 stron (150 tys. wierszy), skoro nowych zdarzeń jest kilkaset?"**
  — `timestamp` w API to znacznik MODYFIKACJI rekordu, nie data zdarzenia: ACLED
  codziennie koryguje wstecznie tysiące starych zdarzeń. Pobieramy nowe + korekty;
  deduplikacja w silver (najnowsza wersja wygrywa, SCD typ 1) sprawia, że korekta
  zastępuje starą wersję zamiast ją duplikować. Dlatego licznik rośnie o setki,
  nie o 150 tysięcy.
- **„Jak cofnęliście dane do pokazu?"** — przyrost bronze to osobny folder dnia;
  revert = przeniesienie folderu do backupu + cofnięcie znacznika; warstwy wyżej
  odbudowują się deterministycznie z bronze. To zresztą dowód na wartość
  warstwy bronze (append-only = pełna odtwarzalność).
