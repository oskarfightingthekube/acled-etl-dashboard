# Screeny do oddania projektu — instrukcja

Wymóg zadania: *„Na screenach powinien być uchwycony moment udanej operacji
ładowania każdego z wymiarów oraz ładowania faktów."* Screeny wrzucamy do
katalogu `screeny/` w repo.

Nasze ładowania = zadania DAG-a `acled_pipeline` w Airflow (task per wymiar +
fakt + walidacja). Jak zrobić komplet:

1. Uruchom Airflow: `cd airflow && docker compose up -d` → `http://localhost:8080`
   (hasło: `docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated`).
2. DAG `acled_pipeline` → **Trigger** → poczekaj na zielono (~2 min).
3. **Screen 1 — graf całości:** widok *Graph*, wszystkie zadania zielone
   (`success`), widoczne nazwy: `gold_events_wide`, `dim_country`, `dim_date`,
   `dim_event_type`, `dim_actor`, `dim_source`, `dim_interaction`,
   `dim_population_year`, `fact_events`, `validate`.
4. **Screeny 2–9 — po jednym na każdy wymiar:** klik zadania (np. `dim_country`)
   → zakładka **Logs** → screen z widocznym `Marking task as SUCCESS` i nazwą
   zadania. Powtórz dla wszystkich 7 wymiarów + `dim_date`.
5. **Screen 10 — fakty:** to samo dla `fact_events`.
6. **Screen 11 — walidacja:** log `validate` (assert: 2 669 096 zdarzeń,
   2 346 465 fatalities — dowód poprawności ładowania).
7. (Opcjonalnie, mocne) **Screen 12 — Athena:** zapytanie
   `SELECT count(*), sum(fatalities) FROM acled_dev.fact_events` z wynikiem.

Nazewnictwo plików: `screeny/01_graf.png`, `screeny/02_dim_country.png`, …
`screeny/10_fact_events.png`, `screeny/11_validate.png`.
