terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.52"
    }
  }

  required_version = ">= 1.15"
}

provider "aws" {
  region = "eu-central-1"
}
