
output "bronze_bucket" {
  description = "S3 bucket name for bronze layer (raw CSV)"
  value       = aws_s3_bucket.bronze.bucket
}

output "silver_bucket" {
  description = "S3 bucket name for silver layer (Parquet)"
  value       = aws_s3_bucket.silver.bucket
}

output "gold_bucket" {
  description = "S3 bucket name for gold layer (star schema)"
  value       = aws_s3_bucket.gold.bucket
}

output "glue_database" {
  description = "Glue Catalog database name"
  value       = aws_glue_catalog_database.acled.name
}

output "glue_role_arn" {
  description = "IAM Role ARN for Glue jobs"
  value       = aws_iam_role.glue_role.arn
}
