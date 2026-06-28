locals {
  env = terraform.workspace
}

variable "project_prefix" {
  description = "Prefix for globally unique S3 bucket names"
  type        = string
  default     = "mw-acled"
}
