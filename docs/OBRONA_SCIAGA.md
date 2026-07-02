# Ściąga na obronę — hurtownia danych ACLED

Egzamin = rozmowa o projekcie. Ten dokument: pełna opowieść, decyzje z
uzasadnieniami, twarde liczby, prawdopodobne pytania z odpowiedziami, scenariusz
demo i słabe punkty z liniami obrony.

---

## 0. Pitch na 30 sekund

Zbudowaliśmy hurtownię danych o konfliktach zbrojnych na **realnych danych
ACLED** (2,67 mln zdarzeń, 1997–2025) wzbogaconych o populację z World Banku.
Architektura to **lakehouse na AWS w układzie medalionu** (bronze→silver→gold),
orkiestrowany **Apache Airflow**, z **czystym schematem gwiazdy** w warstwie
gold, **modelem semantycznym i raportami w Power BI**. Całość odpowiada na
**12 pytań biznesowych** i waliduje się automatycznie przy każdym uruchomieniu.

---

## 1. Dane źródłowe i pytania biznesowe

- **ACLED** (Armed Conflict Location & Event Data) — publiczny, ekspercki
  rejestr zdarzeń konfliktowych: bitwy, protesty, zamieszki, przemoc wobec
  cywilów, ostrzały. Dane NIE są generowane — pobieramy z oficjalnego API
  (wymóg projektu). Zakres: 1997–2025, cały świat, ~2,67 mln zdarzeń po deduplikacji
  (rośnie przyrostowo; 2 669 294 na 2.07.2026).
- **World Bank, wskaźnik SP.POP.TOTL** — populacja kraj×rok (6 235 wierszy,
  215 krajów), do pytań per capita.
- **12 pytań biznesowych** (README): geografia i skala (Q1–2), trendy czasowe
  i sezonowość (Q3–4), typy zdarzeń i stosunek protestów pokojowych do
  przemocy (Q5–6), aktorzy i interakcje (Q7–8), celowanie w cywilów (Q9),
  źródła (Q10), eskalacja YoY (Q11), per capita (Q12).

**Może spytać: „dlaczego ten temat?"** — dane są realne, duże (miliony
wierszy — hurtownia ma sens), mają naturalne wymiary (czas, geografia, typ,
aktor) i addytywną miarę (ofiary), a pytania per capita wymuszają integrację
dwóch niezależnych źródeł — czyli pełne ćwiczenie z integracji danych.

---

## 2. Architektura — warstwa po warstwie

```
ACLED API ──(1) Python ingest──► BRONZE (S3, surowe CSV, append-only)
                                    │ (2) Glue Crawler → katalog acled_dev
                                    ▼
                         (3) Glue Job (Spark): dedup + typy + delete'y
                                    ▼
                          SILVER (S3, Parquet, 1 wiersz = 1 zdarzenie)
                                    │
              (4) Athena CTAS: gold_events_wide (integracja + czyszczenie)
                                    ▼
              (5) Athena CTAS: SCHEMAT GWIAZDY (fact_events + 7 wymiarów)
                                    ▼
                  (6) Power BI: model semantyczny (DAX) + raporty
        ────────────────────────────────────────────────────────────
        Orkiestracja kroków 2–5: Apache Airflow (DAG acled_pipeline)
        + task `validate` (rekoncyliacja warstw po każdym runie)
```

### 2.1 Ekstrakcja (E) — `src/ingest.py`
- OAuth do API ACLED, paginacja po 5 000 rekordów.
- **Ładowanie przyrostowe**: stan ostatniego pobrania w
  `state/last_run_timestamp.txt`; przy kolejnym runie bierzemy tylko rekordy
  z nowszym znacznikiem czasu. To metoda „informacja o czasie wprowadzenia
  dostępna w źródle" z wykładu o ETL.
- Osobno pobieramy **rejestr usunięć** (`deletes`) — ACLED publikuje ID
  rekordów skasowanych; przechowujemy je, żeby silver mógł je odfiltrować.

### 2.2 Bronze — surowość i nieulotność
- Surowe CSV, **append-only, nigdy nie modyfikujemy** — archiwum i siatka
  bezpieczeństwa do reprocessingu (definicyjna *nieulotność* hurtowni wg
  Inmona zaczyna się u nas już tutaj).
- Glue Crawler kataloguje pliki → tabele `events` i `deletes` w bazie
  `acled_dev` (katalog Glue = nasze **metadane techniczne**).

### 2.3 Silver — jedna wersja prawdy
- Job **AWS Glue (Spark)**, `glue/silver_transform.py`:
  - **deduplikacja**: `row_number() OVER (PARTITION BY event_id_cnty ORDER BY
    timestamp DESC) = 1` — najnowsza wersja zdarzenia wygrywa. To w praktyce
    **SCD typ 1** (nadpisujemy starą wartość, nie trzymamy historii zmian
    rekordu — bo do analiz liczy się aktualny stan zdarzenia),
  - **anti-join z `deletes`** — usuwamy skasowane,
  - typowanie (daty, inty, double),
  - zapis do **Parquet** (kolumnowy, kompresowany — patrz pyt. o wydajność).
- Wynik: jeden wiersz na zdarzenie (2 669 294 na 2.07.2026); duplikaty
  i delete'y usuwane przy każdym zasileniu.

### 2.4 Gold — integracja i czyszczenie (`sql/06`)
- `gold_events_wide` = oczyszczona, szeroka tabela zdarzeń w Athena:
  - liczby i teksty **z silvera** (patrz sekcja 4 — root cause),
  - kolumna `interaction` dosztukowana **z bronze** (w silverze zepsuta
    castem do INT),
  - flaga `civilian_targeting_flag` 0/1,
  - `NULLIF`/`COALESCE` na pseudo-nullach.
- Do tego rollupy per-pytanie (gold_geography, gold_actors, …) — pełnią rolę
  **agregacji / perspektyw zmaterializowanych** z wykładu: wstępnie policzone
  podsumowania przyspieszające typowe analizy. W Power BI ich nie importujemy
  (tam liczy DAX na gwieździe) — są uzasadnieniem doboru wymiarów i miar oraz
  niezależną ścieżką weryfikacji wyników.

### 2.5 Schemat gwiazdy (`sql/10`) — serce projektu
- **Temat**: zdarzenia konfliktów. **Ziarnistość**: jedno zdarzenie (fakt
  transakcyjny). **Miary**: `fatalities` (addytywna), `civilian_targeting_flag`
  (0/1, addytywna — sumą jest liczba zdarzeń wymierzonych w cywilów).
- **Fakt `fact_events`** (~2,67 mln): WYŁĄCZNIE klucze wymiarów + miary
  (Zasada nr 1 z wykładu 3) + `event_id_cnty` jako **wymiar zdegenerowany**
  (unikalny per wiersz — dokładnie jak „NrZamówienia" z wykładu).
- **7 wymiarów, wszystkie z kluczami sztucznymi**:
  | Wymiar | Wiersze | Klucz | Uwagi |
  |---|---|---|---|
  | dim_country | 242 | `id_country` (surogat) | iso, kraj, region; hierarchia Region→Kraj |
  | dim_date | 10 592 | `id_date` = yyyymmdd | **ciągły kalendarz** 1997–2025 (sequence), rok/kwartał/miesiąc |
  | dim_event_type | 26 | surogat | hierarchia disorder→event→sub-event |
  | dim_actor | 16 494 | surogat | aktor pierwszy zdarzenia |
  | dim_source | 1 874 | surogat | skala źródła (lokalne…międzynarodowe) |
  | dim_interaction | 134 | surogat | para typów aktorów; **normalny wymiar**, nie zdegenerowany (za mała liczność) |
  | dim_population_year | 6 235 | `iso_year` = iso·10000+rok | klucz złożony spłaszczony do 1 kolumny (relacje Power BI są jednokolumnowe) |
- **Wiersz „Unknown" (id = −1)** w każdym wymiarze — pseudo-nulle mapowane na
  wartość znaczącą (dokładnie wg wykładu o jakości danych).
- Zasady z wykładu: ≤25 wymiarów ✓ (7), fakt istotnie największy ✓ (~160×
  większy od największego wymiaru), miary sumowalne ✓.
- Hurtownia **jednotematyczna** → czysta gwiazda, bez bus matrix (ta jest
  potrzebna dopiero przy wielu tabelach faktów i uzgadnianiu wymiarów).

### 2.6 Warstwa semantyczna — Power BI
- Import tabel gwiazdy „na płasko" (`SELECT *` przez ODBC/Athena, tryb
  **Import** — dane małe po stronie modelu, DAX w pełni funkcjonalny, szybkie
  wizualizacje; DirectQuery odpalałby Athenę i naliczał koszty przy każdym
  kliknięciu).
- 7 relacji **wiele-do-jednego** (wymiar po stronie „1", filtr pojedynczy —
  wymiar filtruje fakty, nigdy odwrotnie).
- ~15 **miar DAX**: `Total Events` (COUNTROWS), `Total Fatalities` (SUM),
  `Fatalities per Event` (DIVIDE), `Pct Civilian Targeting`,
  `Peaceful/Violent + Ratio` (CALCULATE — zmiana kontekstu filtra),
  `Events LY` i `YoY Events %` (DATEADD po oznaczeniu dim_date jako tabeli
  dat), `Distinct Actors/Countries` (DISTINCTCOUNT), `Events per 100k`.
- **Hierarchie** (drill-down): Rok→Kwartał→Miesiąc, Region→Kraj,
  Disorder→Event→Sub-event; miesiące sortowane po numerze (nie alfabetycznie!).
- Jeden model = wszystkie 12 pytań (slicery + zmiana wymiaru na osi), zamiast
  12 hardkodowanych zapytań SQL.

### 2.7 Raporty — Power BI
- Strona **Dashboard** na początku (karty KPI: zdarzenia, ofiary, % cywile,
  liczba aktorów + trend), potem strony per pytanie.
- Elementy z zajęć: slicery **zsynchronizowane** między stronami, drill-down,
  **heatmapa** (formatowanie warunkowe na macierzy sezonowości), interakcje
  między wizualizacjami, przyciski nawigacyjne, tytuły + czytelne legendy.

### 2.8 Orkiestracja — Apache Airflow
- Lokalny Airflow (docker-compose), DAG `acled_pipeline`:
  `ingest → crawler → silver(Glue) → gold_events_wide → 7 wymiarów →
  fact_events → validate`.
- **Idempotencja**: każdy krok Athena = DROP TABLE IF EXISTS + wyczyszczenie
  prefixu S3 + CTAS → DAG można odpalać wielokrotnie, także na żywo na obronie.
- Task **`validate`** kończy każdy run assertami inwariantów (sekcja 5).
- Gałąź Glue (crawler+silver) za parametrem `run_glue` (wymaga uprawnień
  glue:* — ścieżka Athena działa bez nich; silver i tak jest już policzony).

---

## 3. Kluczowe decyzje i uzasadnienia („dlaczego tak?")

| Decyzja | Uzasadnienie |
|---|---|
| **Lakehouse (S3+Athena) zamiast SQL Server** | dozwolony stack z dokumentu ARCHITEKTURA (wariant „Airflow → chmurowy magazyn → SQL/Views → Power BI"); dane 2,7 mln wierszy, format kolumnowy Parquet + silnik zapytań bez serwera; medalion = wprost z wykładu 2 |
| **Gwiazda, nie płatek śniegu** | zalecenie z wykładu („czysty model gwiazdy dla hurtowni jednotematycznej"); Kimball: płatek psuje wydajność i czytelność; nasze hierarchie (region→kraj, disorder→event→sub) mieszczą się w zdenormalizowanych wymiarach |
| **Klucze sztuczne (surogaty)** | wzorzec z wykładu (IdCzasu, IdKlienta…); izolują model od zmian kluczy naturalnych; int szybszy w złączeniach; klucz daty yyyymmdd = standardowy „smart key" |
| **`interaction` jako pełny wymiar** | 134 wartości — wg definicji z wykładu wymiar zdegenerowany wolno stosować tylko przy liczności porównywalnej z faktem; `event_id_cnty` (2,67 mln unikalnych) — ten kwalifikuje się jako zdegenerowany |
| **Ciągły kalendarz w dim_date** | z DISTINCT dat byłyby dziury → Power BI „Mark as date table" i funkcje czasowe (DATEADD/YoY) wymagają ciągłości |
| **`iso_year` = iso·10000+rok** | populacja ma klucz złożony (kraj, rok), a relacje Power BI są jednokolumnowe — spłaszczamy bezkolizyjnie (iso ≤ 3 cyfry) |
| **Wiersz Unknown(−1)** | wykład o jakości: pseudo-nulle w wymiarach zamieniamy na wartość znaczącą; bez tego zdarzenia bez przypisania znikałyby z analiz |
| **Import, nie DirectQuery w PBI** | pełny DAX, szybkie raporty, zero kosztów skanowania Atheny przy klikaniu; dane odświeżamy po runie ETL |
| **Airflow, nie SSIS** | jawnie dopuszczony w wymaganiach; kod w Pythonie w repo (wersjonowalny), UI z grafem na demo, idempotentne kroki |

---

## 4. Historia jakości danych (nasz najmocniejszy punkt — opowiedzieć!)

1. **Objaw:** przy przepinaniu gwiazdy suma ofiar wyszła **324 225**, a
   niezależna ścieżka (rollup ze silvera) dawała **2 346 465** — 7× różnicy,
   mimo że liczba zdarzeń zgadzała się co do wiersza.
2. **Root cause:** ACLED eksportuje CSV z wartościami w cudzysłowach.
   SerDe Atheny czytający bronze (LazySimpleSerDe) nie zdejmuje cudzysłowów:
   w kolumnach tekstowych zostawały (`"Ukraine"`), a **kolumny liczbowe
   stawały się NULL-ami** — `"12"` nie parsuje się do BIGINT. Spark w jobie
   silver parsuje CSV poprawnie — dlatego silver miał dobre liczby.
3. **Drugi bug (odwrotny):** job silver castuje `interaction` (etykieta
   tekstowa, np. „State forces-Rebel group") do INT → NULL **w plikach**
   silvera. Czyli: bronze-przez-Athenę psuje liczby, silver psuje jedną
   kolumnę tekstową.
4. **Fix — hybryda:** `gold_events_wide` bierze wszystko z silvera (przez
   nową deklarację `silver_events_full` — dane w plikach zawsze były
   kompletne, brakowało tylko kolumn w DDL), a `interaction` z bronze
   (dedup + zdjęcie cudzysłowów + `NULLIF('')` → puste do Unknown).
5. **Wniosek systemowy:** walidujemy **dwie** metryki, nie jedną —
   liczba wierszy **i** suma miary. Sama liczba wierszy maskowała ubytek.
   Task `validate` w DAG-u pilnuje obu przy każdym runie.

To jest żywy przykład na: kontrolę jakości ekstrakcji („czy dane nie ulegają
uszkodzeniu?"), integrację formatów i wartość rekoncyliacji niezależnych
ścieżek liczenia — wszystko z wykładów o ETL i jakości danych.

---

## 5. Twarde liczby (wykuć)

| Liczba | Co to |
|---|---|
| **2 669 294** | zdarzeń po dedup (stan 2.07.2026; rekoncyliacja: silver==gold==fakt) |
| **2 346 567** | suma ofiar (stan 2.07.2026; druga metryka rekoncyliacji) |
| ~2,67 mln po dedup | duplikaty + delete'y usuwane przy każdym zasileniu |
| 1997–2025 | zakres danych; 10 592 dni w dim_date |
| 242 / 26 / 16 494 / 1 874 / 134 / 6 235 | wiersze wymiarów (kraj / typ / aktor / źródło / interakcja / populacja) |
| 431 695 | zdarzenia z celowaniem w cywilów (~16%) |
| Ukraina, Indie, Syria | top kraje wg zdarzeń |
| Ukraina 2022: **+35 176** | największy skok YoY (inwazja); Birma 2021: +17 340 (pucz) |
| Palestyna **400,9/100k** | per capita 2024 — ranking odwraca się (#10 absolutnie → #1) |
| State forces–Rebel group: **611 920** ofiar | najkrwawsza interakcja |
| Afryka Środkowa ~38% | najwyższy odsetek celowania w cywilów |
| Angola 1 350 | największe pojedyncze zdarzenie (bitwa, 2001) |

---

## 6. Prawdopodobne pytania + odpowiedzi

**OLTP vs OLAP — różnice?** OLTP: dużo małych transakcji, dane bieżące,
znormalizowany schemat, użytkownik = pracownik operacyjny. OLAP: mało zapytań,
ale na ogromnych danych; dane historyczne, zagregowane; schemat
zdenormalizowany (u nas gwiazda); użytkownik = analityk. Nasza hurtownia to
czysty OLAP — źródło (API ACLED) gra rolę systemu „operacyjnego".

**Definicja hurtowni wg Inmona — 4 cechy i gdzie u nas?**
zorientowana na temat (konflikty zbrojne — nie „obsługa pobierania z API"),
zintegrowana (ACLED + World Bank, wspólne kody ISO, jednolite typy),
nieulotna (bronze append-only; gold odtwarzalny deterministycznie),
zróżnicowana czasowo (29 lat historii, każdy fakt ma datę, wymiar czasu).

**Inmon czy Kimball?** Podejście Kimballa (bottom-up): zdenormalizowana
hurtownia wymiarowa budowana od konkretnego obszaru biznesowego. Mała skala
projektu i szybkie iteracje — dokładnie zalety Kimballa z wykładu.

**ROLAP, MOLAP czy model tabelaryczny?** ROLAP w warstwie Athena (gwiazda w
tabelach relacyjnych, zapytania SQL) + **model tabelaryczny** w Power BI
(kolumnowy, in-memory, kompresja słownikowa/RLE — stąd 2,67 mln wierszy działa
płynnie na laptopie). MOLAP (kostka) nie — mała elastyczność, my potrzebujemy
zapytań ad hoc.

**Co to ziarnistość i jaka jest u was?** Poziom szczegółowości faktu —
u nas jedno zdarzenie (fakt transakcyjny). Aksjomat: każdy wiersz faktu ma tę
samą ziarnistość ✓. Drobniejsze ziarno = więcej analiz, ale więcej danych;
nasze pytania wymagają poziomu zdarzenia (mapa, aktorzy), więc nie agregujemy.

**Rodzaje miar — wasze są addytywne?** `fatalities` — w pełni addytywna
(suma ma sens po każdym wymiarze). `civilian_targeting_flag` — 0/1, suma =
liczba zdarzeń z celowaniem ✓. Wskaźniki typu „% cywilów" czy „ofiary na
zdarzenie" to miary **nieaddytywne II rodzaju** (najpierw suma, potem iloraz) —
dlatego NIE siedzą w fakcie, tylko liczy je DAX (DIVIDE po agregacji).

**Klasyfikacja wymiarów — przykłady u was?** Zdegenerowany: `event_id_cnty`
(jedno pole, liczność = fakt). Uzgodniony: czas/kraj (gdyby doszła druga
tabela faktów, te wymiary by się współdzieliło — bus matrix). Wielokrotnego
stosowania: u nas nie występuje (jedna data na zdarzenie), ale to np. data
zamówienia/wysyłki podpinana 2× do faktu. Abstrakcyjny (junk): nie mamy —
liczba wymiarów mała.

**SCD — jak rejestrujecie historię?** Typ 1 (nadpisanie): dedup „najnowszy
timestamp wygrywa" + tabela `deletes`. Świadomy wybór: ACLED koryguje opisy
zdarzeń — analitycznie liczy się wersja aktualna, nie historia korekt.
Gdyby wymagano pełnej historii — typ 2 (nowy wiersz per wersja z zakresem
dat obowiązywania); umiem opisać typy 0–7 (0 stałe, 1 nadpisz, 2 nowy wiersz,
3 kolumna „poprzednia wartość", 4 osobna tabela historii / miniwymiar dla
szybkozmiennych, 6=1+2+3, 7 podejście hybrydowe).

**Fazy ETL i VIM?** Ekstrakcja (API, przyrostowo po timestamp), Transformacja
(dedup, typy, czyszczenie cudzysłowów, flagi, Unknown — czyli **W**alidacja,
**I**ntegracja formatów i semantyczna, **M**apowanie: tabela mapowań w
`docs/etl_mapowania.md`), Ładowanie (CTAS wymiarów, potem faktu z lookupem
surogatów; początkowe = pełne przebudowy, przyrostowe = ingest po znaczniku).

**Wykrywanie zmian w źródle?** Źródło odpytywalne z informacją o czasie zmiany
(kolumna `timestamp` w API) + jawny rejestr usunięć (`deletes`) = wariant
„tablicy różnic". Reakcja w hurtowni: INSERT→INSERT, UPDATE→nadpisanie (SCD1),
DELETE→fizyczne usunięcie w silverze (bronze zachowuje wszystko — nieulotność
na poziomie archiwum).

**Optymalizacja zapytań — co stosujecie?** Parquet = przechowywanie
**kolumnowe** + kompresja (odpowiednik indeksów projekcji); rollupy gold =
**agregacje/perspektywy zmaterializowane**; model tabelaryczny PBI = kompresja
słownikowa + RLE in-memory; Athena skanuje tylko potrzebne kolumny. Partycji
nie robimy — przy 2,7 mln wierszy Parquet koszt skanu jest pomijalny; przy
wzroście danych partycjonowalibyśmy po roku (partycjonowanie zakresowe).

**Metadane — gdzie?** Techniczne: katalog Glue (schematy tabel, lokalizacje,
formaty). Operacyjne: logi runów Airflow + wyniki `validate` (czasy, statusy).
Biznesowe: README (pytania, opis modelu), tabela mapowań, opisy miar w modelu
PBI. Rozproszone w narzędziach — dokładnie tak, jak wykład opisuje praktykę.

**Jakość danych — miary i co zrobiliście?** Dokładność/kompletność: inwarianty
2 669 096 / 2 346 465 + audyt nulli i cudzysłowów kolumna po kolumnie;
spójność: jednolite typy w silverze; pseudo-nulle → „Unknown"; kontrola
poprawności ładowania: FK bez sierot (0), unikalność surogatów, automatyczny
`validate` po każdym runie. Plus cała historia z sekcji 4.

**Warstwa semantyczna — czym jest i z czego się składa?** Logiczna warstwa
między hurtownią a narzędziami BI, tłumaczy dane techniczne na pojęcia
biznesowe, daje „jedną wersję prawdy". Elementy u nas: wymiary, hierarchie,
miary DAX, reguły biznesowe (definicja „celowania w cywilów", protest pokojowy
vs przemoc), pola wyliczane, KPI (karty na dashboardzie).

**Data lake vs data warehouse vs lakehouse?** Lake: surowe dane każdego
formatu, tanio, schema-on-read, ryzyko „bagna". Warehouse: przetworzone,
ustrukturyzowane, schema-on-write. Lakehouse łączy: dane w tanim object
storage (S3) + warstwa tabel i SQL nad nimi (Athena/Glue Catalog) — nasz
przypadek; medalion bronze/silver/gold to wzorzec organizacji lakehouse'a
(wykład 2, slajd o architekturze medalionu).

**Czemu nie SSAS/SSIS jak na laboratoriach?** Wymagania jawnie dopuszczają
zamienniki: Airflow (integracja), model Power BI (semantyka), Power BI
(raporty). Merytorycznie: te same pojęcia (miary, wymiary, hierarchie,
kalkulacje) — inna technologia.

**Wizualizacja — jakich zasad pilnujecie?** Zero-baseline dla słupków,
chronologiczna oś czasu (sort miesięcy po numerze), bez 3D i kołowych nadużyć,
heatmapa dla macierzy gęstych, maksymalizacja data-ink (Tufte), tytuły +
duże legendy, drill-down od ogółu do szczegółu.

---

## 7. Słabe punkty i linie obrony (pytania „z haczykiem")

| Zarzut | Obrona |
|---|---|
| „Silver ma zepsutą kolumnę interaction" | Znany bug (INT-cast w Glue), udokumentowany w sql/06; obejście hybrydą z bronze; docelowy fix = usunięcie castów i re-run joba — nie zdążył przed oddaniem, bo wymaga uprawnień glue:* |
| „Podwójne czyszczenie: Glue i Athena robią dedup" | Świadoma redundancja na czas projektu: silver = kanoniczny clean (Glue), CTE w gold = ta sama logika dla kolumny ratowanej z bronze; po zjeździe zostaje tylko ścieżka silver |
| „Czemu lat/long nie ma w gwieździe?" | Zasada 1: fakt = klucze+miary; współrzędne zostały w gold_events_wide — mapa w raportach idzie po kraju (choropleta), punktowa możliwa z gold |
| „Rollupy dublują gwiazdę" | Rola: agregaty (perspektywy zmaterializowane) + uzasadnienie wymiarów/miar + niezależna ścieżka weryfikacji (to one wykryły błąd fatalities) |
| „Kosowo nie ma per capita" | ISO 3166 nie nadaje Kosowu kodu numerycznego → brak wiersza populacji WB; 0,65% zdarzeń; totale zdarzeń nietknięte (LEFT JOIN) |
| „2025 niepełny w YoY" | Dane do 2025-06-29; na wykresach YoY zaznaczamy rok częściowy |
| „Ingest na żywo?" | Wymaga konta ACLED (.env); pokazujemy kod + stan bronze + resztę pipeline'u live |

---

## 8. Scenariusz demo (5 minut, przećwiczyć raz)

1. **README** — pytania biznesowe + diagram architektury (`images/architecture.png`).
2. **Diagram gwiazdy** (`images/star_schema.png`) — omów fakt/wymiary/klucze.
3. **Airflow** (`docker compose up -d`, `localhost:8080`) — Trigger DAG
   (bez `run_glue`) → zielony graf w ~2 min → pokaż log `validate`.
4. **Athena** — `SELECT count(*), sum(fatalities) FROM acled_dev.fact_events`
   → liczby zgodne między warstwami (rekoncyliacja).
5. **Power BI** — widok modelu (gwiazda!), miara w DAX, dashboard, drill-down
   Rok→Kwartał→Miesiąc, slicer, mapa.
6. Puenta: historia z cudzysłowami (sekcja 4) — pokazuje, że rozumiemy nie
   tylko narzędzia, ale i dane.
