# ACLED ETL — hurtownia danych (monorepo)

| Katalog | Zawartość |
|---|---|
| [`main/`](main/README.md) | pipeline: ekstrakcja (Python), Glue (silver), SQL warstwy gold + **schemat gwiazdy**, Terraform, diagramy |
| [`airflow/`](airflow/README.md) | orkiestracja: DAG `acled_manual_backfill` (ingest→silver) + DAG `acled_pipeline` (gold→gwiazda→walidacja) |
| [`powerbi/`](powerbi/README.md) | projekt Power BI (PBIP): model semantyczny + raporty |
| [`docs/`](docs/) | tabela mapowań ETL, spec warstwy semantycznej, status projektu, ściąga na obronę |
| [`screeny/`](screeny/) | screeny udanego ładowania wymiarów i faktów (wymóg zadania) |

Architektura, schemat gwiazdy i pytania biznesowe: [`main/README.md`](main/README.md).
