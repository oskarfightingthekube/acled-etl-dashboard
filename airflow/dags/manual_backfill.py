from airflow.sdk import Param

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.operators.glue_crawler import GlueCrawlerOperator
from datetime import datetime

from main.src.ingest import event_load, delete_load
from main.src.settings import Settings

settings = Settings()

dag = DAG(
    dag_id="acled_manual_backfill",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["acled", "manual"],
    params={
        "full": Param(default=False, type="boolean", description="Full or incremental"),
    },
)


def _delete_load_wrapper(**context):
    return delete_load(full=context["params"]["full"])


def _event_load_wrapper(**context):
    return event_load(full=context["params"]["full"])


def _check_new_data(**context):
    ti = context["ti"]
    delete_count = ti.xcom_pull(task_ids="delete_load") or 0
    event_count = ti.xcom_pull(task_ids="event_load") or 0

    total = delete_count + event_count
    if total == 0:
        return False

    return True


run_delete_load = PythonOperator(
    task_id="delete_load",
    python_callable=_delete_load_wrapper,
    dag=dag,
)

run_event_load = PythonOperator(
    task_id="event_load",
    python_callable=_event_load_wrapper,
    dag=dag,
)

check_new_data = ShortCircuitOperator(
    task_id="check_new_data",
    python_callable=_check_new_data,
    dag=dag,
)

run_crawler_events = GlueCrawlerOperator(
    task_id="run_bronze_crawler_events",
    config={"Name": f"acled-bronze-events-{settings.environment}"},
    wait_for_completion=True,
    dag=dag,
)

run_crawler_deletes = GlueCrawlerOperator(
    task_id="run_bronze_crawler_deletes",
    config={"Name": f"acled-bronze-deletes-{settings.environment}"},
    wait_for_completion=True,
    dag=dag,
)

silver_transform = GlueJobOperator(
    task_id="silver_transform",
    job_name=f"acled-silver-transform-{settings.environment}",
    script_args={
        "--database": settings.glue_database,
        "--silver_bucket": settings.s3_silver_bucket,
    },
    dag=dag,
)

# sekwencyjnie, nie równolegle: ACLED przy wydaniu tokena unieważnia poprzedni,
# więc dwa równoległe loginy nawzajem ubijają sobie sesje (401 w trakcie paginacji)
run_delete_load >> run_event_load >> check_new_data >> [run_crawler_events, run_crawler_deletes] >> silver_transform