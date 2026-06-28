resource "aws_s3_bucket" "bronze" {
  bucket = "${var.project_prefix}-bronze-${local.env}"

  tags = {
    Layer       = "bronze"
    Environment = local.env
    Project     = "acled-pipeline"
  }
}

resource "aws_s3_bucket" "silver" {
  bucket = "${var.project_prefix}-silver-${local.env}"

  tags = {
    Layer       = "silver"
    Environment = local.env
    Project     = "acled-pipeline"
  }
}

resource "aws_s3_bucket" "gold" {
  bucket = "${var.project_prefix}-gold-${local.env}"

  tags = {
    Layer       = "gold"
    Environment = local.env
    Project     = "acled-pipeline"
  }
}

resource "aws_glue_catalog_database" "acled" {
  name = "acled_${local.env}"
}


resource "aws_iam_role" "glue_role" {
  name = "acled-glue-role-${local.env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = local.env
    Project     = "acled-pipeline"
  }
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3_access" {
  name = "acled-glue-s3-access-${local.env}"
  role = aws_iam_role.glue_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.bronze.arn,
          "${aws_s3_bucket.bronze.arn}/*",
          aws_s3_bucket.silver.arn,
          "${aws_s3_bucket.silver.arn}/*",
          aws_s3_bucket.gold.arn,
          "${aws_s3_bucket.gold.arn}/*"
        ]
      }
    ]
  })
}
