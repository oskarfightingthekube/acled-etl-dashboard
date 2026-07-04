"""ACLED ETL — bronze -> (Glue silver) -> gold_events_wide -> czysty schemat gwiazdy.

Idempotentny: przed każdym CTAS robi DROP TABLE IF EXISTS + czyści prefix S3,
więc DAG można odpalać wielokrotnie (bare CREATE TABLE padłby przy 2. runie).

SQL trzymany inline — TRZYMAĆ W SYNCU z main/sql/06_gold_conflict.sql i
main/sql/10_star_schema.sql (źródło prawdy = pliki sql/).

Źródła (root cause udokumentowany w main/sql/06): silver ma poprawne fatalities
i czyste stringi, bronze-przez-Athena ma interaction; gold_events_wide = hybryda.
Walidacja po każdym runie: rekoncyliacja warstw (silver == gold == fakt,
liczba zdarzeń i suma fatalities) — odporna na przyrostowe zasilanie.

Gałąź Glue (crawler + silver job) jest opt-in (param run_glue), bo wymaga
uprawnień glue:*. Ścieżka Athena-only działa z Athena+S3+Glue-Data-Catalog.

UWAGA: dim_population (źródłowy TSV World Bank) i silver_events_full (DDL nad
istniejącym parquetem) to jednorazowy setup (main/sql/07, main/sql/06) — celowo POZA
DAG-iem, żeby nic nie czyściło ich danych.
"""
from __future__ import annotations

import time

import boto3
import pendulum
from airflow.exceptions import AirflowSkipException

try:  # Airflow 3.x
    from airflow.sdk import Param, dag, task, get_current_context
except ImportError:  # Airflow 2.x
    from airflow.decorators import dag, task
    from airflow.models.param import Param
    from airflow.operators.python import get_current_context

REGION = "eu-central-1"
DB = "acled_dev"
GOLD_BUCKET = "mw-acled-gold-dev"
ATHENA_OUT = f"s3://{GOLD_BUCKET}/athena-results/"
WORKGROUP = "primary"
SILVER_GLUE_JOB = "acled-silver-transform-dev"
BRONZE_CRAWLERS = ["acled-bronze-events-dev", "acled-bronze-deletes-dev"]


def _athena(sql: str) -> str:
    """Run one Athena statement, block until done, raise on failure. Returns query id."""
    c = boto3.client("athena", region_name=REGION)
    qid = c.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DB},
        ResultConfiguration={"OutputLocation": ATHENA_OUT},
        WorkGroup=WORKGROUP,
    )["QueryExecutionId"]
    while True:
        st = c.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if st["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            if st["State"] != "SUCCEEDED":
                raise RuntimeError(f"Athena {st['State']}: {st.get('StateChangeReason')}")
            return qid
        time.sleep(2)


def _rebuild(table: str, prefix: str, ctas_body: str) -> None:
    """Idempotent CTAS: drop table, wipe its S3 prefix, re-create."""
    t0 = time.time()
    print(f">> {table}: DROP starej wersji + czyszczenie s3://{GOLD_BUCKET}/{prefix}")
    _athena(f"DROP TABLE IF EXISTS {DB}.{table}")
    boto3.resource("s3", region_name=REGION).Bucket(GOLD_BUCKET).objects.filter(
        Prefix=prefix
    ).delete()
    print(f">> {table}: CREATE TABLE AS SELECT (Athena CTAS)...")
    _athena(
        f"CREATE TABLE {DB}.{table} WITH (format='PARQUET', "
        f"external_location='s3://{GOLD_BUCKET}/{prefix}') AS {ctas_body}"
    )
    qid = _athena(f"SELECT count(*) FROM {DB}.{table}")
    n = boto3.client("athena", region_name=REGION).get_query_results(
        QueryExecutionId=qid)["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"]
    print(f">> {table}: gotowa — {int(n):,} wierszy, {time.time() - t0:.0f} s".replace(",", " "))


GOLD_EVENTS_WIDE = """
WITH bronze_interaction AS (
    SELECT event_id_cnty, NULLIF(trim(replace(interaction, '"', '')), '') AS interaction
    FROM (SELECT event_id_cnty, interaction,
                 row_number() OVER (PARTITION BY event_id_cnty ORDER BY timestamp DESC) rn
          FROM acled_dev.events)
    WHERE rn = 1
)
SELECT
    s.event_id_cnty, s.event_date, s.year,
    s.country, s.region, s.admin1,
    s.event_type, s.sub_event_type, s.disorder_type,
    s.actor1, s.actor2,
    b.interaction,
    CASE WHEN s.civilian_targeting = 'Civilian targeting' THEN 1 ELSE 0 END
        AS civilian_targeting_flag,
    s.latitude, s.longitude, s.iso, s.source_scale,
    s.fatalities
FROM acled_dev.silver_events_full s
LEFT JOIN bronze_interaction b ON s.event_id_cnty = b.event_id_cnty
"""

# wymiary z surogatami + wiersz Unknown (id = -1); patrz main/sql/10
DIMS = {
    "dim_country": (
        "star/dim_country/",
        "SELECT ROW_NUMBER() OVER (ORDER BY iso) id_country, iso, country, region "
        "FROM (SELECT iso, arbitrary(country) country, arbitrary(region) region "
        "FROM acled_dev.gold_events_wide WHERE iso IS NOT NULL GROUP BY iso) "
        "UNION ALL SELECT -1, NULL, 'Unknown', 'Unknown'",
    ),
    "dim_event_type": (
        "star/dim_event_type/",
        "SELECT ROW_NUMBER() OVER (ORDER BY sub_event_type) id_event_type, "
        "sub_event_type, event_type, disorder_type "
        "FROM (SELECT sub_event_type, arbitrary(event_type) event_type, "
        "arbitrary(disorder_type) disorder_type FROM acled_dev.gold_events_wide "
        "WHERE sub_event_type IS NOT NULL GROUP BY sub_event_type) "
        "UNION ALL SELECT -1, 'Unknown', 'Unknown', 'Unknown'",
    ),
    "dim_actor": (
        "star/dim_actor/",
        "SELECT ROW_NUMBER() OVER (ORDER BY actor) id_actor, actor "
        "FROM (SELECT DISTINCT actor1 actor FROM acled_dev.gold_events_wide "
        "WHERE actor1 IS NOT NULL) UNION ALL SELECT -1, 'Unknown'",
    ),
    "dim_source": (
        "star/dim_source/",
        "SELECT ROW_NUMBER() OVER (ORDER BY source_scale) id_source, source_scale "
        "FROM (SELECT DISTINCT source_scale FROM acled_dev.gold_events_wide "
        "WHERE source_scale IS NOT NULL) UNION ALL SELECT -1, 'Unknown'",
    ),
    "dim_interaction": (
        "star/dim_interaction/",
        "SELECT ROW_NUMBER() OVER (ORDER BY interaction) id_interaction, interaction "
        "FROM (SELECT DISTINCT interaction FROM acled_dev.gold_events_wide "
        "WHERE interaction IS NOT NULL) UNION ALL SELECT -1, 'Unknown'",
    ),
    "dim_population_year": (
        "star/dim_population_year/",
        "SELECT iso_numeric*10000+year iso_year, iso_numeric iso, year, "
        "country_name, population FROM acled_dev.dim_population",
    ),
}

DIM_DATE = (
    "star/dim_date/",
    "SELECT CAST(date_format(d,'%Y%m%d') AS int) id_date, CAST(d AS date) date_key, "
    "year(d) year, quarter(d) quarter, month(d) month, date_format(d,'%M') month_name "
    "FROM UNNEST(sequence(date '1997-01-01', date '2025-12-31', interval '1' day)) AS t(d)",
)

# fakt: TYLKO klucze wymiarów + miary (Zasada 1 z wykładu); joinuje wymiary,
# więc w DAG-u musi iść PO nich
FACT_EVENTS = """
SELECT
    w.event_id_cnty,
    COALESCE(c.id_country, -1) id_country,
    CAST(date_format(w.event_date,'%Y%m%d') AS int) id_date,
    COALESCE(e.id_event_type, -1) id_event_type,
    COALESCE(a.id_actor, -1) id_actor,
    COALESCE(s.id_source, -1) id_source,
    COALESCE(i.id_interaction, -1) id_interaction,
    CASE WHEN w.iso IS NOT NULL THEN w.iso*10000+w.year END iso_year,
    w.fatalities, w.civilian_targeting_flag
FROM acled_dev.gold_events_wide w
LEFT JOIN acled_dev.dim_country c ON w.iso = c.iso
LEFT JOIN acled_dev.dim_event_type e ON w.sub_event_type = e.sub_event_type
LEFT JOIN acled_dev.dim_actor a ON w.actor1 = a.actor
LEFT JOIN acled_dev.dim_source s ON w.source_scale = s.source_scale
LEFT JOIN acled_dev.dim_interaction i ON w.interaction = i.interaction
"""


@dag(
    dag_id="acled_pipeline",
    schedule=None,  # odpalany ręcznie (Trigger) — na obronę
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Warsaw"),
    catchup=False,
    params={"run_glue": Param(False, type="boolean",
                              description="Crawler + silver Glue job (wymaga uprawnień glue:*)")},
    doc_md=__doc__,
)
def acled_pipeline():

    @task
    def ingest():
        # ponytail: ekstrakcja API->bronze żyje w main/src/ingest.py i wymaga klucza
        # ACLED; w kontenerze demo pomijamy — bronze już jest w S3.
        raise AirflowSkipException(
            "Ingest pominięty — bronze już w S3. Pełny run: python main/main.py na hoście."
        )

    @task(trigger_rule="none_failed")
    def crawl_bronze():
        if not get_current_context()["params"]["run_glue"]:
            raise AirflowSkipException("run_glue=False — pomijam crawlery")
        glue = boto3.client("glue", region_name=REGION)
        for name in BRONZE_CRAWLERS:
            glue.start_crawler(Name=name)
        for name in BRONZE_CRAWLERS:
            while glue.get_crawler(Name=name)["Crawler"]["State"] != "READY":
                time.sleep(10)

    @task(trigger_rule="none_failed")
    def silver_transform():
        if not get_current_context()["params"]["run_glue"]:
            raise AirflowSkipException("run_glue=False — pomijam Glue job")
        glue = boto3.client("glue", region_name=REGION)
        run_id = glue.start_job_run(JobName=SILVER_GLUE_JOB)["JobRunId"]
        while True:
            state = glue.get_job_run(JobName=SILVER_GLUE_JOB, RunId=run_id)["JobRun"]["JobRunState"]
            if state in ("SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"):
                if state != "SUCCEEDED":
                    raise RuntimeError(f"Glue job {state}")
                return
            time.sleep(15)

    @task(trigger_rule="none_failed")
    def gold_events_wide():
        _rebuild("gold_events_wide", "events_wide/", GOLD_EVENTS_WIDE)

    @task
    def dim_date():
        _rebuild("dim_date", *DIM_DATE)

    def dim_task(name):
        @task(task_id=name)
        def _t():
            prefix, body = DIMS[name]
            _rebuild(name, prefix, body)
        return _t()

    @task
    def fact_events():
        _rebuild("fact_events", "star/fact_events/", FACT_EVENTS)

    @task
    def validate():
        """Rekoncyliacja warstw: silver == gold == fakt (liczba zdarzeń ORAZ suma
        fatalities). Odporna na przyrostowe zasilanie — sprawdzamy zgodność
        między warstwami, nie zahardkodowane snapshoty (te pękają, gdy ingest
        dowiezie nowe dane — co jest poprawnym zachowaniem, nie błędem)."""
        c = boto3.client("athena", region_name=REGION)
        qid = c.start_query_execution(
            QueryString=(
                "SELECT 'silver' l, count(*) c, sum(fatalities) f FROM acled_dev.silver_events_full "
                "UNION ALL SELECT 'gold', count(*), sum(fatalities) FROM acled_dev.gold_events_wide "
                "UNION ALL SELECT 'fact', count(*), sum(fatalities) FROM acled_dev.fact_events"
            ),
            QueryExecutionContext={"Database": DB},
            ResultConfiguration={"OutputLocation": ATHENA_OUT},
            WorkGroup=WORKGROUP,
        )["QueryExecutionId"]
        while True:
            st = c.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
            if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(2)
        rows = c.get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"][1:]
        stats = {r["Data"][0]["VarCharValue"]:
                 (int(r["Data"][1]["VarCharValue"]), int(r["Data"][2]["VarCharValue"]))
                 for r in rows}
        for layer, (cnt, fat) in stats.items():
            print(f">> {layer:6s}: {cnt:,} zdarzeń, {fat:,} ofiar".replace(",", " "))
        assert stats["silver"] == stats["gold"] == stats["fact"], f"warstwy niespójne: {stats}"
        assert stats["fact"][0] > 2_600_000, f"podejrzanie mało zdarzeń: {stats['fact'][0]}"
        print(">> OK: silver == gold == fact — warstwy spójne")

    gold = gold_events_wide()
    fact = fact_events()
    ingest() >> crawl_bronze() >> silver_transform() >> gold
    dims = [dim_task(n) for n in DIMS]
    gold >> dims
    dims >> fact
    dim_date() >> fact          # id_date liczony formułą, ale walidujemy po pełnej gwieździe
    fact >> validate()


acled_pipeline()
