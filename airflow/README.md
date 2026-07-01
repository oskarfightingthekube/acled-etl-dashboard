# Airflow — orkiestracja ACLED ETL

Lokalny Airflow (docker-compose) z DAG-iem `acled_pipeline`:

```
ingest(skip) → crawl_bronze → silver_transform → gold_events_wide → 6 tabel gwiazdy
                (Glue, opt-in)   (Glue, opt-in)      (Athena CTAS)     (Athena CTAS)
dim_date (niezależny — czysty kalendarz)
```

Wszystkie kroki Athena są **idempotentne** (DROP + czyszczenie prefixu S3 +
CTAS), więc DAG można odpalać wielokrotnie — np. na żywo na obronie.

## Start

```bash
cd airflow
docker compose up -d
docker compose exec airflow cat /opt/airflow/standalone_admin_password.txt  # hasło
```
UI: http://localhost:8080 (user `admin`). DAG `acled_pipeline` → **Trigger**.

Kredki AWS: montowane z `~/.aws` hosta (read-only). Wymagany profil `default`
z Athena+S3 (to co używamy w projekcie).

## Gałąź Glue (crawler + silver job) — opt-in

Domyślnie pomijana (`run_glue=False` w parametrach Trigger), bo wymaga
uprawnień `glue:*`, których demo-user nie ma. Po dopięciu polityki niżej:
Trigger DAG → ustaw `run_glue=True`.

Polityka IAM do dołączenia userowi/roli Airflow (via konsola IAM przez konto
z adminem):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GlueOrchestration",
      "Effect": "Allow",
      "Action": [
        "glue:StartCrawler", "glue:GetCrawler",
        "glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:GetJob"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassGlueRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::613025569184:role/acled-glue-role-dev"
    }
  ]
}
```
(Athena CTAS używa Glue Data Catalog — Create/DeleteTable — ale to już działa
z obecnymi uprawnieniami, co potwierdza ręczne budowanie gold/gwiazdy.)

## Uwagi

- **`dim_population` celowo NIE jest w DAG-u** — to EXTERNAL TABLE na
  źródłowym TSV (World Bank); czyszczenie jego prefixu = utrata danych.
  Setup jednorazowy: `sql/07_dim_population.sql`.
- SQL w DAG-u jest inline — **trzymać w syncu** z `sql/06` i `sql/10`
  (pliki sql/ = źródło prawdy).
- Rollupy per-pytanie (`sql/02–04`, część `06`) nie są w DAG-u: model Power BI
  jedzie na gwieździe; rollupy zostają jako uzasadnienie wymiarów/miar.
