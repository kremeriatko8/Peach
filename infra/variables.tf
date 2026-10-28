# Required inputs deliberately have no guessed live defaults.
variable "project_name" {
  type        = string
  description = "Existing PROJECT_NAME. Never change resource names during adoption."
  nullable    = false
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,19}$", var.project_name))
    error_message = "Invalid project_name; use the reviewed existing configuration."
  }
}

variable "region" {
  type        = string
  description = "Existing AWS region; current parser boundary supports us-east-1."
  nullable    = false
  validation {
    condition     = var.region == "us-east-1"
    error_message = "Invalid region; use the reviewed existing configuration."
  }
}

variable "aws_account_id" {
  type        = string
  description = "Verified target AWS account ID, supplied only after authorized inventory."
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Invalid aws_account_id; use the reviewed existing configuration."
  }
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Exact existing Cognito prefix; changing it replaces the domain."
  nullable    = false
  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.cognito_domain_prefix))
    error_message = "Invalid cognito_domain_prefix; use the reviewed existing configuration."
  }
}

variable "frontend_origin" {
  type        = string
  description = "Exact deployed HTTPS origin without trailing slash."
  nullable    = false
  validation {
    condition     = can(regex("^https://[A-Za-z0-9.-]+(:[0-9]+)?$", var.frontend_origin))
    error_message = "Invalid frontend_origin; use the reviewed existing configuration."
  }
}

variable "localhost_origin" {
  type        = string
  description = "Exact existing localhost origin without trailing slash."
  nullable    = false
  validation {
    condition     = can(regex("^http://localhost:[0-9]+$", var.localhost_origin))
    error_message = "Invalid localhost_origin; use the reviewed existing configuration."
  }
}

variable "google_enabled" {
  type        = bool
  description = "Match whether Google federation actually exists. Not inferred from a secret."
  nullable    = false
}

variable "google_client_id" {
  type        = string
  description = "Existing Google OAuth ID; empty only when federation is absent."
  nullable    = false
}

variable "google_client_secret" {
  type        = string
  description = "Existing Google secret; sensitive workspace input, empty only without federation."
  nullable    = false
  sensitive   = true
  validation {
    condition     = var.google_enabled ? (length(var.google_client_id) > 0 && length(var.google_client_secret) > 0) : (var.google_client_id == "" && var.google_client_secret == "")
    error_message = "Invalid google_client_secret; use the reviewed existing configuration."
  }
}

variable "cognito_jwks_json" {
  type        = string
  description = "Verified current public Cognito JWKS snapshot; compare to the deployed Lambdas."
  nullable    = false
  validation {
    condition     = can(jsondecode(var.cognito_jwks_json).keys[0].kid)
    error_message = "Invalid cognito_jwks_json; use the reviewed existing configuration."
  }
}

variable "reports_image_uri" {
  type        = string
  description = "Exact deployed reporting container digest; no newest-image lookup."
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.us-east-1\\.amazonaws\\.com/.+@sha256:[a-f0-9]{64}$", var.reports_image_uri))
    error_message = "Invalid reports_image_uri; use the reviewed existing configuration."
  }
}

variable "parser_image_uri" {
  type        = string
  description = "Exact deployed parser container digest, independently inventoried."
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.us-east-1\\.amazonaws\\.com/.+@sha256:[a-f0-9]{64}$", var.parser_image_uri))
    error_message = "Invalid parser_image_uri; use the reviewed existing configuration."
  }
}

variable "reports_architecture" {
  type        = string
  description = "Existing reporting Lambda architecture."
  nullable    = false
  validation {
    condition     = contains(["arm64", "x86_64"], var.reports_architecture)
    error_message = "Invalid reports_architecture; use the reviewed existing configuration."
  }
}

variable "parser_architecture" {
  type        = string
  description = "Existing parser Lambda architecture."
  nullable    = false
  validation {
    condition     = contains(["arm64", "x86_64"], var.parser_architecture)
    error_message = "Invalid parser_architecture; use the reviewed existing configuration."
  }
}

variable "vpc_id" {
  type        = string
  description = "Existing reporting VPC; Terraform does not manage the VPC."
  nullable    = false
  validation {
    condition     = can(regex("^vpc-[a-f0-9]+$", var.vpc_id))
    error_message = "Invalid vpc_id; use the reviewed existing configuration."
  }
}

variable "subnet_ids" {
  type        = list(string)
  description = "Exact existing builder subnets."
  nullable    = false
  validation {
    condition     = length(var.subnet_ids) > 0 && alltrue([for id in var.subnet_ids : can(regex("^subnet-[a-f0-9]+$", id))])
    error_message = "Invalid subnet_ids; use the reviewed existing configuration."
  }
}

variable "route_table_ids" {
  type        = list(string)
  description = "All existing route tables associated with the selected subnets."
  nullable    = false
  validation {
    condition     = length(var.route_table_ids) > 0 && alltrue([for id in var.route_table_ids : can(regex("^rtb-[a-f0-9]+$", id))])
    error_message = "Invalid route_table_ids; use the reviewed existing configuration."
  }
}

variable "backend_function_security_group_ids" {
  type        = list(string)
  description = "Existing builder security groups; no new DB ingress."
  nullable    = false
  validation {
    condition     = length(var.backend_function_security_group_ids) > 0 && alltrue([for id in var.backend_function_security_group_ids : can(regex("^sg-[a-f0-9]+$", id))])
    error_message = "Invalid backend_function_security_group_ids; use the reviewed existing configuration."
  }
}

variable "database_url" {
  type        = string
  description = "Existing report-builder DB URL. Sensitive workspace input; stored in state."
  nullable    = false
  sensitive   = true
  validation {
    condition     = startswith(var.database_url, "postgresql+asyncpg://")
    error_message = "Invalid database_url; use the reviewed existing configuration."
  }
}

variable "report_owner_sub" {
  type        = string
  description = "Existing configured owner. Sensitive workspace input."
  nullable    = false
  sensitive   = true
  validation {
    condition     = length(var.report_owner_sub) > 0 && length(var.report_owner_sub) <= 128
    error_message = "Invalid report_owner_sub; use the reviewed existing configuration."
  }
}

variable "report_scope_id" {
  type        = string
  description = "Existing opaque report scope; do not rotate during migration."
  nullable    = false
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,47}$", var.report_scope_id))
    error_message = "Invalid report_scope_id; use the reviewed existing configuration."
  }
}

variable "report_recipient_email" {
  type        = string
  description = "Existing SES recipient; sensitive workspace input."
  nullable    = false
  sensitive   = true
  validation {
    condition     = can(regex("^[^ @<>;,]+@[^ @<>;,]+\\.[^ @<>;,]+$", var.report_recipient_email))
    error_message = "Invalid report_recipient_email; use the reviewed existing configuration."
  }
}

variable "report_from_email" {
  type        = string
  description = "Existing SES sender; sensitive workspace input."
  nullable    = false
  sensitive   = true
  validation {
    condition     = can(regex("^[^ @<>;,]+@[^ @<>;,]+\\.[^ @<>;,]+$", var.report_from_email))
    error_message = "Invalid report_from_email; use the reviewed existing configuration."
  }
}

variable "allow_direct_events" {
  type        = bool
  description = "Exact deployed reporting direct-event setting."
  nullable    = false
}

variable "report_schedule_state" {
  type        = string
  description = "Exact live state; template default DISABLED is not evidence of live state."
  nullable    = false
  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.report_schedule_state)
    error_message = "Invalid report_schedule_state; use the reviewed existing configuration."
  }
}

variable "parser_role_name" {
  type        = string
  description = "Exact physical name of the CloudFormation-generated parser role."
  nullable    = false
  validation {
    condition     = length(var.parser_role_name) > 0 && length(var.parser_role_name) <= 64
    error_message = "Invalid parser_role_name; use the reviewed existing configuration."
  }
}

variable "parser_enabled" {
  type        = bool
  description = "Exact live parser enabled flag; never infer from template default."
  nullable    = false
}

variable "parser_frontend_origins" {
  type        = list(string)
  description = "Exact existing function URL CORS origins."
  nullable    = false
  validation {
    condition     = length(var.parser_frontend_origins) > 0 && alltrue([for origin in var.parser_frontend_origins : can(regex("^https://[A-Za-z0-9.-]+(:[0-9]+)?$|^http://localhost:[0-9]+$", origin))])
    error_message = "Invalid parser_frontend_origins; use the reviewed existing configuration."
  }
}

variable "parser_model" {
  type        = string
  description = "Existing model; migration must preserve the Lab 6 substitution."
  nullable    = false
  validation {
    condition     = var.parser_model == "amazon.nova-lite-v1:0"
    error_message = "Invalid parser_model; use the reviewed existing configuration."
  }
}

variable "inference_resource_arn" {
  type        = string
  description = "Exact existing in-region inference ARN."
  nullable    = false
  validation {
    condition     = var.inference_resource_arn == "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0"
    error_message = "Invalid inference_resource_arn; use the reviewed existing configuration."
  }
}

variable "input_usd_per_million" {
  type        = number
  description = "Existing parser pricing setting; migration does not update rates."
  nullable    = false
  validation {
    condition     = var.input_usd_per_million >= 0.000001
    error_message = "Invalid input_usd_per_million; use the reviewed existing configuration."
  }
}

variable "output_usd_per_million" {
  type        = number
  description = "Existing parser pricing setting; migration does not update rates."
  nullable    = false
  validation {
    condition     = var.output_usd_per_million >= 0.000001
    error_message = "Invalid output_usd_per_million; use the reviewed existing configuration."
  }
}


variable "mailer_s3_statement_id" {
  type        = string
  description = "Exact existing mailer Lambda policy Sid; inventory before importing."
  nullable    = false
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,100}$", var.mailer_s3_statement_id))
    error_message = "Use the existing Lambda policy statement ID."
  }
}
variable "parser_url_statement_id" {
  type        = string
  description = "Exact existing InvokeFunctionUrl policy Sid."
  nullable    = false
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,100}$", var.parser_url_statement_id))
    error_message = "Use the existing Lambda policy statement ID."
  }
}
variable "parser_invoke_statement_id" {
  type        = string
  description = "Exact existing InvokedViaFunctionUrl policy Sid."
  nullable    = false
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,100}$", var.parser_invoke_statement_id))
    error_message = "Use the existing Lambda policy statement ID."
  }
}
variable "report_notification_id" {
  type        = string
  description = "Exact existing S3 Lambda notification ID; preserve generated identifiers."
  nullable    = false
  validation {
    condition     = length(var.report_notification_id) > 0
    error_message = "Use the existing S3 notification ID."
  }
}

variable "adoption_inventory_complete" {
  type        = bool
  description = "Keep false until the complete live inventory/import mapping has been reviewed. Set true in the approved HCP workspace only."
  default     = false
  nullable    = false
}

variable "cognito_email_constraints" {
  type        = object({ min_length = string, max_length = string })
  nullable    = false
  description = "Exact deployed email schema string constraints. Required to prevent provider schema replacement drift."
  validation {
    condition     = can(tonumber(var.cognito_email_constraints.min_length)) && can(tonumber(var.cognito_email_constraints.max_length))
    error_message = "Supply the existing Cognito email string constraints from reviewed inventory."
  }
}
