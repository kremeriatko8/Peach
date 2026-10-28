# Synthetic fixtures only. Mocked plan runs never configure AWS or access services.
mock_provider "aws" {
  override_during = plan

  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:123456789012:log-group:test-only" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:us-east-1:123456789012:test-only" }
  }
  mock_resource "aws_cognito_user_pool" {
    defaults = { id = "us-east-1_TESTONLY" }
  }
  mock_resource "aws_cognito_user_pool_client" {
    defaults = { id = "testonlyclient" }
  }
}

variables {
  adoption_inventory_complete         = true
  project_name                        = "peach"
  region                              = "us-east-1"
  aws_account_id                      = "123456789012"
  cognito_domain_prefix               = "test-only-peach"
  frontend_origin                     = "https://test-only.example.com"
  localhost_origin                    = "http://localhost:3000"
  cognito_email_constraints           = { min_length = "0", max_length = "2048" }
  google_enabled                      = true
  google_client_id                    = "test-only-client"
  google_client_secret                = "test-only-secret"
  cognito_jwks_json                   = "{\"keys\":[{\"kid\":\"test-only\"}]}"
  reports_image_uri                   = "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-only@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  parser_image_uri                    = "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-only@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  reports_architecture                = "arm64"
  parser_architecture                 = "arm64"
  vpc_id                              = "vpc-12345678"
  subnet_ids                          = ["subnet-12345678"]
  route_table_ids                     = ["rtb-12345678"]
  backend_function_security_group_ids = ["sg-12345678"]
  database_url                        = "postgresql+asyncpg://test-only:test-only@localhost/test_only"
  report_owner_sub                    = "test-only-owner"
  report_scope_id                     = "test-only-scope"
  report_recipient_email              = "recipient@example.com"
  report_from_email                   = "sender@example.com"
  allow_direct_events                 = false
  report_schedule_state               = "DISABLED"
  parser_role_name                    = "test-only-generated-parser-role"
  parser_enabled                      = true
  parser_frontend_origins             = ["https://test-only.example.com"]
  parser_model                        = "amazon.nova-lite-v1:0"
  inference_resource_arn              = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0"
  input_usd_per_million               = 1
  output_usd_per_million              = 1
  mailer_s3_statement_id              = "test-only-mailer"
  parser_url_statement_id             = "test-only-url"
  parser_invoke_statement_id          = "test-only-invoke"
  report_notification_id              = "test-only-notification"
}

run "preserve_auth_and_report_safety" {
  command = plan
  assert {
    condition     = aws_cognito_user_pool.main.user_pool_tier == "ESSENTIALS" && aws_cognito_user_pool.main.username_configuration[0].case_sensitive == false && aws_cognito_user_pool_client.frontend.generate_secret == false
    error_message = "Cognito must preserve sign-in and the public PKCE client."
  }
  assert {
    condition     = toset(aws_cognito_user_pool_client.frontend.callback_urls) == toset(["https://test-only.example.com/auth/callback/", "http://localhost:3000/auth/callback/"]) && length(aws_cognito_identity_provider.google) == 1
    error_message = "Preserve Google federation and both callback URLs."
  }
  assert {
    condition     = aws_s3_bucket.reports.force_destroy == false && aws_s3_bucket_public_access_block.reports.block_public_acls && aws_s3_bucket_public_access_block.reports.block_public_policy && aws_s3_bucket_public_access_block.reports.ignore_public_acls && aws_s3_bucket_public_access_block.reports.restrict_public_buckets
    error_message = "Reports must remain private and must not be force-deleted."
  }
  assert {
    condition     = aws_sqs_queue.work.visibility_timeout_seconds >= 6 * aws_lambda_function.builder.timeout && jsondecode(aws_sqs_queue.work.redrive_policy).maxReceiveCount == 3 && aws_lambda_event_source_mapping.builder.scaling_config[0].maximum_concurrency == 2
    error_message = "Preserve reporting retry and concurrency settings."
  }
  assert {
    condition     = aws_scheduler_schedule.weekly.state == "DISABLED" && aws_scheduler_schedule.weekly.schedule_expression_timezone == "Europe/Kyiv" && aws_scheduler_schedule.weekly.schedule_expression == "cron(0 7 ? * MON *)"
    error_message = "Migration must preserve configured schedule state and timezone."
  }
  assert {
    condition     = aws_lambda_function.parser.environment[0].variables.PARSER_ENABLED == "true" && length(aws_lambda_function.parser.vpc_config) == 0 && !contains(keys(aws_lambda_function.parser.environment[0].variables), "DATABASE_URL") && !contains(keys(aws_lambda_function.mailer.environment[0].variables), "DATABASE_URL")
    error_message = "Parser enabled state is explicit; parser and mailer must not gain DB access."
  }
  assert {
    condition     = aws_lambda_permission.parser_invoke.invoked_via_function_url && aws_lambda_permission.parser_url.function_url_auth_type == "NONE" && aws_lambda_function_url.parser.cors[0].allow_methods == toset(["POST"])
    error_message = "Preserve both URL permissions and CORS."
  }
  assert {
    condition     = aws_lambda_function.builder.image_uri == var.reports_image_uri && aws_lambda_function.mailer.image_uri == var.reports_image_uri && aws_lambda_function.parser.image_uri == var.parser_image_uri
    error_message = "Reporting and parser images must preserve independent immutable digests."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.parser.policy).Statement[0].Action == "bedrock:InvokeModel" && aws_iam_role.parser.permissions_boundary == "arn:aws:iam::123456789012:policy/PeachAgendaParserBoundary"
    error_message = "Preserve the parser permission boundary and inference scope."
  }
}

run "preserve_inventory_queue_and_google_settings" {
  command = plan
  variables { report_schedule_state = "ENABLED" }
  assert {
    condition = alltrue([
      aws_sqs_queue.builder_dlq.max_message_size == 1048576,
      aws_sqs_queue.work.max_message_size == 1048576,
      aws_sqs_queue.scheduler_dlq.max_message_size == 1048576,
      aws_sqs_queue.mailer_failure.max_message_size == 1048576
    ])
    error_message = "Do not shrink the live 1 MiB queues to the provider's 256 KiB default."
  }
  assert {
    condition = aws_cognito_identity_provider.google[0].attribute_mapping == tomap({
      email = "email", email_verified = "email_verified", name = "name", picture = "picture", username = "sub"
    })
    error_message = "Preserve the complete existing Google mapping, including username=sub."
  }
  assert {
    condition = length(aws_cognito_identity_provider.google[0].provider_details) == 9 && alltrue([
      aws_cognito_identity_provider.google[0].provider_details.attributes_url == "https://people.googleapis.com/v1/people/me?personFields=",
      aws_cognito_identity_provider.google[0].provider_details.attributes_url_add_attributes == "true",
      aws_cognito_identity_provider.google[0].provider_details.authorize_scopes == "openid email profile",
      aws_cognito_identity_provider.google[0].provider_details.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth",
      aws_cognito_identity_provider.google[0].provider_details.oidc_issuer == "https://accounts.google.com",
      aws_cognito_identity_provider.google[0].provider_details.token_request_method == "POST",
      aws_cognito_identity_provider.google[0].provider_details.token_url == "https://www.googleapis.com/oauth2/v4/token"
    ])
    error_message = "Preserve all observed Google provider details without hardcoding credentials."
  }
  assert {
    condition     = aws_scheduler_schedule.weekly.state == "ENABLED" && aws_lambda_function.parser.environment[0].variables.PARSER_ENABLED == "true"
    error_message = "Adoption must preserve the enabled live schedule and parser."
  }
}

run "preserve_absent_google_and_enabled_schedule" {
  command = plan
  variables {
    google_enabled        = false
    google_client_id      = ""
    google_client_secret  = ""
    parser_enabled        = false
    report_schedule_state = "ENABLED"
  }
  assert {
    condition     = length(aws_cognito_identity_provider.google) == 0 && aws_cognito_user_pool_client.frontend.supported_identity_providers == toset(["COGNITO"]) && aws_scheduler_schedule.weekly.state == "ENABLED" && aws_lambda_function.parser.environment[0].variables.PARSER_ENABLED == "false"
    error_message = "Conditional federation, parser and schedule settings must follow inventory."
  }
}

run "unreviewed_adoption_is_blocked" {
  command = plan
  variables { adoption_inventory_complete = false }
  # Root failures stop downstream graph evaluation; only evaluated failures are expected.
  expect_failures = [
    aws_cloudwatch_log_group.parser,
    aws_iam_role.parser,
    aws_cognito_user_pool.main,
    aws_sqs_queue.builder_dlq,
    aws_sqs_queue.scheduler_dlq,
    aws_sqs_queue.mailer_failure,
    aws_dynamodb_table.mail_state,
    aws_cloudwatch_log_group.builder,
    aws_cloudwatch_log_group.mailer,
    aws_iam_role.builder,
    aws_iam_role.mailer,
    aws_s3_bucket.reports,
    aws_vpc_endpoint.reports_s3,
    aws_scheduler_schedule_group.reports
  ]
}

run "reject_incomplete_google_credentials" {
  command = plan
  variables { google_client_secret = "" }
  expect_failures = [var.google_client_secret]
}
