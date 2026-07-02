import sys
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql.functions import col, row_number
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ["JOB_NAME","database", "silver_bucket"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

events_df = glueContext.create_dynamic_frame.from_catalog(
    database="acled_dev",
    table_name="events",
).toDF()

deletes_df = glueContext.create_dynamic_frame.from_catalog(
    database="acled_dev",
    table_name="deletes",
).toDF()

window = Window.partitionBy("event_id_cnty").orderBy(col("timestamp").desc())
deduped = (
    events_df
    .withColumn("rn", row_number().over(window))
    .filter("rn = 1")
    .drop("rn")
)

deleted_ids = deletes_df.select("event_id_cnty")
cleaned = deduped.join(deleted_ids, on="event_id_cnty", how="left_anti")

silver = (
    cleaned
    .withColumn("event_date", col("event_date").cast("date"))
    .withColumn("year", col("year").cast("int"))
    .withColumn("time_precision", col("time_precision").cast("int"))
    .withColumn("inter1", col("inter1").cast("int"))
    .withColumn("inter2", col("inter2").cast("int"))
    .withColumn("interaction", col("interaction").cast("int"))
    .withColumn("fatalities", col("fatalities").cast("int"))
    .withColumn("iso", col("iso").cast("int"))
    .withColumn("latitude", col("latitude").cast("double"))
    .withColumn("longitude", col("longitude").cast("double"))
    .withColumn("geo_precision", col("geo_precision").cast("int"))
    .drop("timestamp")
)

silver_path = f"s3://{args['silver_bucket']}/events/"
silver.write.mode("overwrite").parquet(silver_path)

job.commit()