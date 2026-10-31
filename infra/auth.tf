resource "aws_cognito_user_pool" "main" {
  name                     = "${var.project_name}-users"
  user_pool_tier           = "ESSENTIALS"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OFF"
  username_configuration { case_sensitive = false }
  admin_create_user_config { allow_admin_create_user_only = false }
  email_configuration { email_sending_account = "COGNITO_DEFAULT" }
  verification_message_template { default_email_option = "CONFIRM_WITH_CODE" }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
  schema {
    name                = "email"
    attribute_data_type = "String"
    string_attribute_constraints {
      min_length = var.cognito_email_constraints.min_length
      max_length = var.cognito_email_constraints.max_length
    }
    required = true
    mutable  = true
  }
  tags = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_cognito_identity_provider" "google" {
  count         = var.google_enabled ? 1 : 0
  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "Google"
  provider_type = "Google"
  # Preserve the complete Google configuration observed on 2026-10-27.
  provider_details = {
    client_id                     = var.google_client_id
    client_secret                 = var.google_client_secret
    attributes_url                = "https://people.googleapis.com/v1/people/me?personFields="
    attributes_url_add_attributes = "true"
    authorize_scopes              = "openid email profile"
    authorize_url                 = "https://accounts.google.com/o/oauth2/v2/auth"
    oidc_issuer                   = "https://accounts.google.com"
    token_request_method          = "POST"
    token_url                     = "https://www.googleapis.com/oauth2/v4/token"
  }
  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    name           = "name"
    picture        = "picture"
    username       = "sub"
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${var.project_name}-frontend"
  user_pool_id = aws_cognito_user_pool.main.id
  # Create-only in provider 6.70.0: imports leave this null. Explicit false
  # would replace the existing secretless public client. Preserve its identity.
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["${var.frontend_origin}/auth/callback/", "${var.localhost_origin}/auth/callback/"]
  logout_urls                          = ["${var.frontend_origin}/", "${var.localhost_origin}/"]
  supported_identity_providers         = concat(["COGNITO"], aws_cognito_identity_provider.google[*].provider_name)
  read_attributes                      = ["email", "email_verified", "name", "picture"]
  write_attributes                     = ["email", "name", "picture"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  user_pool_id          = aws_cognito_user_pool.main.id
  domain                = var.cognito_domain_prefix
  managed_login_version = 2
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_cognito_managed_login_branding" "frontend" {
  user_pool_id                = aws_cognito_user_pool.main.id
  client_id                   = aws_cognito_user_pool_client.frontend.id
  use_cognito_provided_values = true
  depends_on                  = [aws_cognito_user_pool_domain.main]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}
