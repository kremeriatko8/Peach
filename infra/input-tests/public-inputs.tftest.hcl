# Run only through terraform-check.sh with the observed PUBLIC tfvars.
# No real secret values are read; every missing credential/private setting is synthetic.
mock_provider "aws" { override_during = plan }
variables {
  google_client_id       = "test-only-client"
  google_client_secret   = "test-only-secret"
  database_url           = "postgresql+asyncpg://test-only:test-only@localhost/test_only"
  report_owner_sub       = "test-only-owner"
  report_from_email      = "sender@example.com"
  report_recipient_email = "recipient@example.com"
  cognito_jwks_json      = "{\"keys\":[{\"kid\":\"test-only\"}]}"
}
run "public_inputs_are_valid_and_adoption_stays_blocked" {
  command = plan
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
  assert {
    condition = jsonencode({
      adoption_inventory_complete         = var.adoption_inventory_complete
      project_name                        = var.project_name
      region                              = var.region
      aws_account_id                      = var.aws_account_id
      cognito_domain_prefix               = var.cognito_domain_prefix
      frontend_origin                     = var.frontend_origin
      localhost_origin                    = var.localhost_origin
      google_enabled                      = var.google_enabled
      cognito_email_constraints           = var.cognito_email_constraints
      reports_image_uri                   = var.reports_image_uri
      parser_image_uri                    = var.parser_image_uri
      reports_architecture                = var.reports_architecture
      parser_architecture                 = var.parser_architecture
      vpc_id                              = var.vpc_id
      subnet_ids                          = var.subnet_ids
      route_table_ids                     = var.route_table_ids
      backend_function_security_group_ids = var.backend_function_security_group_ids
      report_scope_id                     = var.report_scope_id
      allow_direct_events                 = var.allow_direct_events
      report_schedule_state               = var.report_schedule_state
      parser_role_name                    = var.parser_role_name
      parser_enabled                      = var.parser_enabled
      parser_frontend_origins             = var.parser_frontend_origins
      parser_model                        = var.parser_model
      inference_resource_arn              = var.inference_resource_arn
      input_usd_per_million               = var.input_usd_per_million
      output_usd_per_million              = var.output_usd_per_million
      mailer_s3_statement_id              = var.mailer_s3_statement_id
      parser_url_statement_id             = var.parser_url_statement_id
      parser_invoke_statement_id          = var.parser_invoke_statement_id
      report_notification_id              = var.report_notification_id
    }) == jsonencode(jsondecode(file("${path.module}/input-tests/observed-public-inputs.json")).observed_public_inputs)
    error_message = "All 31 public inputs must match the recorded inventory; do not guess or silently change existing settings."
  }
  assert {
    condition     = var.adoption_inventory_complete == false && var.aws_account_id == "968053399627" && var.region == "us-east-1" && var.google_enabled && var.parser_enabled && var.report_schedule_state == "ENABLED"
    error_message = "Observed inputs must preserve the account and enabled services, with adoption blocked."
  }
  assert {
    condition     = var.reports_image_uri != var.parser_image_uri && var.cognito_email_constraints.min_length == "0" && var.cognito_email_constraints.max_length == "2048"
    error_message = "Preserve the distinct deployed images and observed Cognito email schema."
  }
}
