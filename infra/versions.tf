terraform {
  required_version = ">= 1.13.5, < 2.0"
  # User-confirmed existing workspace. Binding this explicitly prevents accidental
  # selection of another organization/workspace through ambient CLI variables.
  # This declaration does not initialize or modify HCP/state during local checks.
  cloud {
    organization = "ooad-kremeriatko8"
    workspaces {
      name = "peach-dev"
    }
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.70.0"
    }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.aws_account_id]
  # No static credentials or profile. HCP supplies dynamic AWS credentials.
  # No new default tags during adoption: they would cause non-import changes.
}

locals {
  partition      = "aws"
  reports_bucket = "${var.project_name}-reports-${var.aws_account_id}-${var.region}"
  report_prefix  = "arn:${local.partition}:s3:::${local.reports_bucket}/reports/${var.report_scope_id}/*.csv"
  authority      = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  cognito_domain = "https://${var.cognito_domain_prefix}.auth.${var.region}.amazoncognito.com"
}
