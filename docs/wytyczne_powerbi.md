# Wytyczne prowadzącej do Power BI — co, dlaczego i jak spełniamy

Źródła: jej skrypt „Power BI – model semantyczny i raport analityczny"
(bloki 1–6) + wykład 8 (wizualizacja danych). Przy każdej wytycznej jej
uzasadnienie (parafraza ze skryptu) i stan u nas.

## A. Model danych (blok 1)

| Wytyczna | Dlaczego (jej uzasadnienie) | U nas |
|---|---|---|
| **Najpierw model, potem wykresy** | „Raport jest wiarygodny tylko wtedy, gdy stoi na poprawnym modelu danych" — wykres na złym modelu liczy źle, choć wygląda dobrze | model zbudowany i zwalidowany przed pierwszym wykresem ✅ |
| **Tryb Import** (nie DirectQuery) | tabela faktów „niezbyt duża" mieści się w pamięci → pełny DAX i szybkie raporty | Import; 2,67 mln wierszy działa płynnie ✅ |
| **Nie ładować tabel technicznych/stagingowych** | model ma zawierać tylko to, czego użyje raport | tylko 8 tabel gwiazdy; bronze/silver/rollupy zostały poza modelem ✅ |
| **Sprawdzić typy danych w Power Query przed załadowaniem** | „czysty start: właściwe tabele i właściwe typy" — złe typy psują agregacje i relacje | typy narzucone już w gwieździe (Athena), w PBI zgodne ✅ |
| **Relacje \*:1, wymiar po stronie 1, filtr POJEDYNCZY** | „wymiar filtruje fakty — nigdy odwrotnie"; filtr w obie strony = wymiary filtrują się nawzajem przez fakt → mniej wydajne i trudne w interpretacji | 7 relacji \*:1; jedyny wyjątek: populacja **Both** — świadomie, bo inaczej filtr kraju nie dochodzi do populacji i per capita liczy się źle (umieć uzasadnić!) ✅ |
| **Ukryć kolumny techniczne (klucze)** | „model budujemy dla użytkownika raportu, nie dla siebie" — nieczytelna lista pól = trudny raport | wszystkie `id_*` ukryte ✅ |
| **Czytelne nazwy pól** | nazwa ma być zrozumiała dla osoby nieznającej struktury bazy | nazwy biznesowe + aliasy na kartach ✅ |

## B. Porządek modelu (blok 2)

| Wytyczna | Dlaczego | U nas |
|---|---|---|
| **Hierarchie wymiarów** (np. Rok→Kwartał→Miesiąc) | umożliwiają drill-down — „podstawowy mechanizm analizy danych w Power BI" | Kalendarz, Region→Kraj, Disorder→Event→Sub ✅ |
| **Foldery wyświetlania** | nie zmieniają modelu — porządkują listę pól dla wygody | miary w folderze „Miary" ✅ |
| **Miary zamiast gołych kolumn** | miara „liczy się dynamicznie w zależności od filtrów i wizualizacji" — jedna miara odpowiada na wiele pytań przez zmianę kontekstu | 15+ miar DAX; wykresy na miarach ✅ |
| **DIVIDE zamiast operatora `/`** | „bezpiecznie obsługuje dzielenie przez zero — dobra praktyka w DAX" | wszystkie ilorazy przez DIVIDE ✅ |
| **Formaty miar** (waluta/liczba/procent) | spójność interpretacji dla odbiorcy | %, separatory, 2 miejsca ✅ |

## C. Pułapki, które wymienia z nazwy (bloki 2–4)

| Wytyczna | Dlaczego | U nas |
|---|---|---|
| **Miesiące sortowane chronologicznie** (Sortuj według kolumny → numer miesiąca) | „sortowanie niechronologiczne w wymiarze czasu to bardzo poważny błąd wizualizacyjny, który wprowadza użytkownika w błąd" | `month_name` sortowane po `month` ✅ |
| **Ta sama wartość na całym wykresie = brak relacji** | jej „szybka pomoc": jeśli wszędzie ta sama liczba — relacja nie działa | relacje zweryfikowane (0 sierot) ✅ |
| **CALCULATE do miar warunkowych** | „policz to… ale tylko dla wybranych danych" — zmiana kontekstu filtra to najważniejsza funkcja DAX | Peaceful/Violent, Events LY ✅ |
| **DISTINCTCOUNT do liczenia encji** | COUNT liczy wiersze; unikalnych klientów/aktorów liczy się DISTINCTCOUNT | Distinct Actors/Countries ✅ |
| **Wiek/grupy liczone względem roku analizy, nie „dzisiaj"** | analiza ma być powtarzalna | nie dotyczy wprost; zasada zachowana w YoY ✅ |

## D. Raport (bloki 4–5)

| Wytyczna | Dlaczego | U nas |
|---|---|---|
| **Slicery dla użytkownika, filtry panelu dla projektanta** | slicer = sterowanie dla odbiorcy; filtr wizualu/strony = decyzja projektanta (np. odcięcie niepełnego roku) | slicery year/region + filtry projektanckie (≤2024, min. N zdarzeń) ✅ |
| **Synchronizacja fragmentatorów** | użytkownik „wybiera rok tylko raz, a cały raport działa w tym samym kontekście" | suwak zsynchronizowany na wszystkich stronach ✅ |
| **Drill-down na hierarchii** | przechodzenie od ogółu do szczegółu bez zmiany strony | macierz kraj→typ, struktura rok→miesiąc ✅ |
| **Formatowanie warunkowe (heatmapa) w macierzy** | „ludzkie oko bardzo szybko wychwytuje rozpiętość skali" z koloru, nie z liczb | heatmapa miesiąc×rok ✅ |
| **Filtr strony zablokowany dla przypadków biznesowych** | wynik ma pokazywać tylko właściwy wycinek (u niej: rok 2011, bankomaty) | filtry min. 50/200/1000 zdarzeń, ≤2024 ✅ |
| **Tytuły stron i wszystkich wizualizacji** | odbiorca ma rozumieć bez znajomości modelu | komplet tytułów z założeniami w nawiasach ✅ |

## E. Dashboard (blok 6)

| Wytyczna | Dlaczego | U nas |
|---|---|---|
| **Dashboard = PIERWSZA strona** | „punkt startowy — najpierw najważniejsze wskaźniki, potem szczegóły" | strona 00 ✅ |
| **Karty KPI w jednym rzędzie u góry** | szybkie podsumowanie sytuacji | 4 karty ✅ |
| **Trend + struktura + segmentacja** | dashboard pokazuje skalę, kierunek i skład — nie wszystko | trend, struktura, TOP-y, scatter ✅ |
| **Interakcje między wizualizacjami** | „wizualizacje rozmawiają ze sobą" — klik filtruje resztę; najważniejszy mechanizm interaktywnej analizy | domyślne włączone; pokazać na obronie ✅ |
| **Przyciski nawigacyjne** | użytkownik nie szuka kart na dole ekranu | boczne menu nawigacyjne ✅ |
| **Dashboard czytelny „w kilka sekund"** | nie służy do pokazania wszystkiego, tylko do zrozumienia sytuacji | zwięzły układ ✅ |

## F. Wykład 8 — zasady wykresów (Tufte/Knaflic)

| Wytyczna | Dlaczego | U nas |
|---|---|---|
| **Słupki od zera** | ucięta oś przekłamuje proporcje | zero-baseline wszędzie ✅ |
| **Liniowy tylko dla ciągłych danych, oś czasu chronologicznie** | linia sugeruje ciągłość; jedna jednostka czasu na wykres | linie tylko na osi czasu ✅ |
| **Bez 3D** | zniekształca odczyt wartości | brak ✅ |
| **Tabela — gdy odbiorca ma CZYTAĆ wartości** | „tabele ludzie czytają, nie oglądają" | rankingi/średnie jako tabele ✅ |
| **Scatter do związku dwóch wielkości** | jednoczesne kodowanie X/Y pokazuje, czy związek istnieje | „więcej zdarzeń ≠ więcej ofiar" ✅ |
| **Maksymalizuj data-ink, usuń nieład** | elementy bez informacji rozpraszają | czyste karty, bez ozdobników ✅ |
| **Skup uwagę / opowiadaj historię** | wykres ma tezę, nie tylko dane | tytuły-wnioski, tabela eskalacji = wydarzenia historyczne ✅ |
