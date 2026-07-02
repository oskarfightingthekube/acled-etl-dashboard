# Warstwa semantyczna + raport Power BI (ACLED) — wg metody z zajęć

Zgodne ze skryptem prowadzącej („Power BI – model semantyczny i raport
analityczny") i wymaganiami projektu. **Cała logika biznesowa jest w modelu
Power BI (relacje + miary DAX + hierarchie), a NIE w SQL.** SQL, którym się
łączymy, jest płaski: import całych tabel gwiazdy (`SELECT * FROM fact_events`
itd.) — bez GROUP BY / WHERE / agregacji.

Rollupy (`gold_geography`, `gold_yearly_trends`, …) i SQL per-pytanie
(`main/sql/05,08,09`) NIE są warstwą semantyczną — to **uzasadnienie**, dlaczego
wybraliśmy te wymiary i miary. Ten sam model odpowiada na wszystkie 12 pytań
przez zmianę wymiaru na osi + slicery, zamiast 12 hardkodowanych zapytań.

## Architektura (na obronę)
`AWS Glue (ETL) → S3 + Athena (lakehouse/warstwa SQL) → gwiazda w Athena →
Power BI (model semantyczny + raport)`. To wariant dozwolonego stacku
„Airflow → Redshift/BigQuery → SQL/Views → Power BI" z dokumentu ARCHITEKTURA.

## 1. Import (płaski) + model gwiazdy
Pobierz dane → ODBC (DSN `ACLED_Athena`) → zaimportuj **tylko** tabele gwiazdy
(8): `fact_events`, `dim_country`, `dim_date`, `dim_event_type`, `dim_actor`,
`dim_source`, `dim_interaction`, `dim_population_year`. Import, nie DirectQuery.

Relacje (Widok modelu), wszystkie **wiele-do-jednego (\*:1)**, filtr pojedynczy,
wymiar po stronie 1 (zweryfikowane: każdy klucz wymiaru unikalny, także
case-insensitive — Power BI ignoruje wielkość liter w kluczach tekstowych):
- `fact_events[id_country]` → `dim_country[id_country]`
- `fact_events[id_date]` → `dim_date[id_date]`
- `fact_events[id_event_type]` → `dim_event_type[id_event_type]`
- `fact_events[id_actor]` → `dim_actor[id_actor]`
- `fact_events[id_source]` → `dim_source[id_source]`
- `fact_events[id_interaction]` → `dim_interaction[id_interaction]`
- `fact_events[iso_year]` → `dim_population_year[iso_year]`

(Klucze sztuczne `id_*` — po imporcie ukryj je w widoku raportu.)

Ukryj klucze techniczne (prawy klik kolumny → Ukryj w widoku raportu).
Oznacz `dim_date` jako tabelę dat: zaznacz `dim_date` → Narzędzia tabeli →
Oznacz jako tabelę dat → kolumna `date_key` (włącza funkcje czasu / YoY).

## 2. Hierarchie (drill-down)
- **dim_date:** prawy klik `year` → Utwórz hierarchię → dodaj `quarter`,
  `month_name`. Hierarchia **Rok → Kwartał → Miesiąc**.
  - Sort chronologiczny: zaznacz `month_name` → Narzędzia kolumny → Sortuj
    według kolumny → `month`. (inaczej miesiące alfabetycznie = błąd)
- **dim_country:** hierarchia **Region → Country** (`region` → dodaj `country`).
- **dim_event_type:** hierarchia **disorder_type → event_type → sub_event_type**.

## 3. Miary DAX (warstwa semantyczna, 10 pkt)
Utwórz w `fact_events` (Modelowanie → Nowa miara). Odpowiadają na 12 pytań:

```DAX
Total Events = COUNTROWS(fact_events)
Total Fatalities = SUM(fact_events[fatalities])
Fatalities per Event = DIVIDE([Total Fatalities], [Total Events])
Civilian Targeting Events = SUM(fact_events[civilian_targeting_flag])
Pct Civilian Targeting = DIVIDE([Civilian Targeting Events], [Total Events])
Distinct Actors = DISTINCTCOUNT(fact_events[id_actor])
Distinct Countries = DISTINCTCOUNT(fact_events[id_country])
```
Miary warunkowe (CALCULATE) — protesty vs przemoc (Q5):
```DAX
Peaceful Protests = CALCULATE([Total Events], dim_event_type[sub_event_type] = "Peaceful protest")
Violent Demonstrations = CALCULATE([Total Events],
    dim_event_type[sub_event_type] IN {"Violent demonstration","Protest with intervention","Excessive force against protesters"})
Peaceful to Violent Ratio = DIVIDE([Peaceful Protests], [Violent Demonstrations])
```
Czas / eskalacja YoY (Q9) — wymaga `dim_date` oznaczonej jako tabela dat:
```DAX
Events LY = CALCULATE([Total Events], DATEADD(dim_date[date_key], -1, YEAR))
YoY Events % = DIVIDE([Total Events] - [Events LY], [Events LY])
```
Format: `Pct Civilian Targeting`, `YoY Events %` → procent; `Fatalities per
Event` → liczba 2 miejsca; reszta liczby całkowite (Narzędzia miary → Format).

### Per capita (Q12)
Obsłużone w gwieździe: `fact_events[iso_year]` → `dim_population_year[iso_year]`
(klucz złożony (iso, rok) spłaszczony do jednej kolumny, bo relacje PBI są
1-kolumnowe). Miary:
```DAX
Population = SUM(dim_population_year[population])
Events per 100k = DIVIDE([Total Events] * 100000, [Population])
Fatalities per 100k = DIVIDE([Total Fatalities] * 100000, [Population])
```
Uwaga: ~0,4% zdarzeń (Kosowo itp.) nie ma populacji → per-capita puste dla nich;
totale zdarzeń nie tracą nic. Zweryfikowane krzyżowo z `gold_per_capita` —
identyczne wyniki (2024: Palestyna 400,9 / Liban 251,8 / Ukraina 147,9 na 100k).

## 4. Raport — 1 strona = 1 pytanie (mapa na 12 pytań)
Wszystko na JEDNYM modelu (measures + slicery + drill-down). Wzorzec ze skryptu:

| Strona | Pytanie | Wizual | Oś / Wiersze | Legenda | Wartości (miara) |
|---|---|---|---|---|---|
| Geografia | Q1 | mapa + słupkowy | dim_country (Region▸Country) | — | Total Events / Total Fatalities |
| Zgony | Q2 | mapa | dim_country[country] | — | Total Fatalities; kolor = Fatalities per Event |
| Trendy | Q3 | liniowy | hierarchia dim_date | dim_event_type[disorder_type] | Total Events |
| Sezonowość | Q4 | macierz + heatmapa | dim_date[month_name] (wiersze), year (kolumny) | — | Total Events (formatowanie warunkowe = kolor tła) |
| Typy zdarzeń | Q5 | słupkowy + KPI | dim_event_type[sub_event_type] | — | Total Fatalities; karta = Peaceful to Violent Ratio |
| Aktorzy | Q6 | słupkowy (Top N) | dim_actor[actor] | — | Total Events / Total Fatalities |
| Interakcje | Q6 | słupkowy | dim_interaction[interaction] | — | Total Fatalities / Fatalities per Event |
| Cywile | Q7 | słupkowy + liniowy | dim_country[region] / dim_date | region | Pct Civilian Targeting |
| Źródła | Q8 | słupkowy skumulowany | dim_country[region] | dim_source[source_scale] | Total Events |
| Eskalacja | Q9 | słupkowy + punktowy | dim_country[country] × dim_date[year] | — | YoY Events % ; scatter: Total Events vs Total Fatalities |
| Per capita | Q12 | mapa + tabela | dim_country[country] | — | Events per 100k |

Elementy wymagane przez skrypt: **slicery** (dim_date[year], region,
disorder_type) zsynchronizowane między stronami (Widok → Synchronizuj
fragmentatory); **drill-down** na hierarchii czasu; **formatowanie warunkowe**
(heatmapa) na macierzy sezonowości; **strona Dashboard** na początku z kartami
KPI (Total Events, Total Fatalities, Distinct Actors, Pct Civilian Targeting).

## 5. Estetyka (styl Maciek + skrypt)
Tytuł każdej strony (pole tekstowe), tytuły wszystkich wizualizacji, duże
czytelne legendy, ukryte pola techniczne, motyw `ACLED_Editorial.json`
(View → Themes → Browse). Zapisz `.pbix`.
