variable "project_id" {
  description = "GCP project ID (permanent, globally unique), e.g. peach-<name>-2026."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "6-30 chars, lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "region" {
  description = "Region for Cloud Run, Cloud SQL and Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "name" {
  description = "Prefix for resource names."
  type        = string
  default     = "peach"
}

variable "api_image_tag" {
  description = "Tag of the backend image in Artifact Registry to deploy to Cloud Run."
  type        = string
  default     = "latest"
}

variable "db_activation_policy" {
  description = "ALWAYS = running (billed per hour), NEVER = stopped (only storage billed)."
  type        = string
  default     = "ALWAYS"

  validation {
    condition     = contains(["ALWAYS", "NEVER"], var.db_activation_policy)
    error_message = "Use ALWAYS (running) or NEVER (stopped)."
  }
}

variable "db_deletion_protection" {
  description = "Keep false for the lab so `terraform destroy` removes the instance."
  type        = bool
  default     = false
}

variable "api_max_instances" {
  description = "Upper bound on Cloud Run instances; with a pool of 5+2 this keeps under db-f1-micro's ~25 connections."
  type        = number
  default     = 2
}

variable "cors_origins" {
  description = "Comma-separated browser origins allowed to call the API directly. Empty = same origin only (Firebase /api/** rewrite)."
  type        = string
  default     = ""
}

# Sign-in stays on AWS (Cognito). The API only verifies Cognito access tokens,
# so it needs the public issuer, client id and JWKS. None of these is a secret.
variable "cognito_authority" {
  description = "Cognito issuer, https://cognito-idp.us-east-1.amazonaws.com/<pool-id> (infra/ output)."
  type        = string
  default     = ""
}

variable "cognito_client_id" {
  description = "Cognito app client id (public)."
  type        = string
  default     = ""
}

variable "cognito_jwks_json" {
  description = "Cognito JWKS document (public keys) as JSON."
  type        = string
  default     = ""
}
