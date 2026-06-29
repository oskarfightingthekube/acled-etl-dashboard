import time
from datetime import datetime

import boto3

from src.client import ACLEDClient
from src.settings import Settings
import logging

logger = logging.getLogger(__name__)
s3 = boto3.client("s3")

settings = Settings()


def _get_last_timestamp():
    try:
        response = s3.get_object(
            Bucket=settings.s3_bronze_bucket,
            Key=settings.s3_last_run_timestamp
        )
        return response["Body"].read().decode().strip()
    except s3.exceptions.NoSuchKey:
        return None


def _save_timestamp():
    s3.put_object(
        Bucket=settings.s3_bronze_bucket,
        Key=settings.s3_last_run_timestamp,
        Body=str(int(time.time())).encode(),
    )


def delete_load(full=True):
    last_ts = None if full else _get_last_timestamp()
    payload = {}
    if last_ts:
        payload["deleted_timestamp"] = last_ts
        payload["deleted_timestamp_where"] = ">="

    with ACLEDClient() as client:
        for page in client.get_pages(url=settings.deleted_data_url,
                                     extra_payload=payload, ):
            key = settings.s3_deletes_prefix.format(
                date=datetime.now().strftime("%Y-%m-%d"),
            )
            s3.put_object(
                Bucket=settings.s3_bronze_bucket,
                Key=key,
                Body=page.encode("utf-8"),
            )
            logger.info(f"uploaded deleted {key}")
        logger.info(f"deleted load completed")


def event_load(full=False):
    if not full:
        last_ts = _get_last_timestamp()
        if last_ts is None:
            logger.warning("no timestamp available, run with full=True first")
            return
        extra_payload = {"timestamp": last_ts, "timestamp_where": ">="}
    else:
        extra_payload = None

    with ACLEDClient() as client:
        for i, page in enumerate(client.get_pages(
                url=settings.read_data_url,
                extra_payload=extra_payload,
        ), 1):
            key = settings.s3_events_prefix.format(
                date=datetime.now().strftime("%Y-%m-%d"),
                page=i,
            )
            s3.put_object(
                Bucket=settings.s3_bronze_bucket,
                Key=key,
                Body=page.encode("utf-8"),
            )
            logger.info(f"uploaded {key}")

    _save_timestamp()
    mode = "full" if full else "incremental"
    logger.info(f"{mode} event load completed")
