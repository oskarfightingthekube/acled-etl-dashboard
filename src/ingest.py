import logging

import boto3

from src.client import ACLEDClient
from src.settings import Settings
import logging
logger = logging.getLogger(__name__)
s3 = boto3.client("s3")


def full_load():
    settings = Settings()
    client = ACLEDClient()
    start_enum = 1
    for i, page in enumerate(client.get_pages(), start_enum):
        key = settings.s3_full_load_prefix.format(page=i)
        s3.put_object(
            Bucket=settings.s3_bronze_bucket,
            Key=key,
            Body=page.encode("utf-8"),
        )

        logger.info(f"uploaded {key}")
    logger.info("full load completed")
