resource "aws_sqs_queue" "builder_dlq" {
  # Preserve the observed AWS setting instead of the provider default.
  max_message_size          = 1048576
  name                      = "${var.project_name}-report-builder-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_sqs_queue_redrive_allow_policy" "builder_dlq" {
  queue_url = aws_sqs_queue.builder_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.work.arn]
  })
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_sqs_queue" "work" {
  # Preserve the observed AWS setting instead of the provider default.
  max_message_size           = 1048576
  name                       = "${var.project_name}-report-work"
  visibility_timeout_seconds = 720
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.builder_dlq.arn
    maxReceiveCount     = 3
  })
  tags = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_sqs_queue" "scheduler_dlq" {
  # Preserve the observed AWS setting instead of the provider default.
  max_message_size          = 1048576
  name                      = "${var.project_name}-report-scheduler-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_sqs_queue" "mailer_failure" {
  # Preserve the observed AWS setting instead of the provider default.
  max_message_size          = 1048576
  name                      = "${var.project_name}-report-mailer-failures"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_dynamodb_table" "mail_state" {
  name         = "${var.project_name}-report-mail-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "report_id"
  attribute {
    name = "report_id"
    type = "S"
  }
  server_side_encryption { enabled = true }
  tags = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_cloudwatch_log_group" "builder" {
  name              = "/aws/lambda/${var.project_name}-report-builder"
  retention_in_days = 7
  tags              = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_cloudwatch_log_group" "mailer" {
  name              = "/aws/lambda/${var.project_name}-report-mailer"
  retention_in_days = 7
  tags              = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_function" "builder" {
  function_name = "${var.project_name}-report-builder"
  package_type  = "Image"
  image_uri     = var.reports_image_uri
  image_config { command = ["app.reporting.builder.handler"] }
  architectures = [var.reports_architecture]
  role          = aws_iam_role.builder.arn
  memory_size   = 512
  timeout       = 120
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.builder.name
  }
  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.backend_function_security_group_ids
  }
  environment {
    variables = {
      DATABASE_URL        = var.database_url
      DB_POOLING          = "false"
      APP_ENV             = "production"
      REPORT_OWNER_SUB    = var.report_owner_sub
      REPORT_SCOPE_ID     = var.report_scope_id
      REPORT_TIMEZONE     = "Europe/Kyiv"
      REPORT_BUCKET       = aws_s3_bucket.reports.bucket
      REPORT_QUEUE_ARN    = aws_sqs_queue.work.arn
      REPORT_ALLOW_DIRECT = tostring(var.allow_direct_events)
    }
  }
  tags       = { PROJECT_NAME = var.project_name }
  depends_on = [aws_iam_role_policy.builder]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_event_source_mapping" "builder" {
  event_source_arn                   = aws_sqs_queue.work.arn
  function_name                      = aws_lambda_function.builder.arn
  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
  enabled                            = true
  scaling_config { maximum_concurrency = 2 }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_function" "mailer" {
  function_name = "${var.project_name}-report-mailer"
  package_type  = "Image"
  image_uri     = var.reports_image_uri
  image_config { command = ["app.reporting.mailer.handler"] }
  architectures = [var.reports_architecture]
  role          = aws_iam_role.mailer.arn
  memory_size   = 256
  timeout       = 60
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.mailer.name
  }
  environment {
    variables = {
      REPORT_SCOPE_ID        = var.report_scope_id
      REPORT_TIMEZONE        = "Europe/Kyiv"
      REPORT_BUCKET          = aws_s3_bucket.reports.bucket
      REPORT_RECIPIENT_EMAIL = var.report_recipient_email
      REPORT_FROM_EMAIL      = var.report_from_email
      REPORT_DEDUP_TABLE     = aws_dynamodb_table.mail_state.name
    }
  }
  tags       = { PROJECT_NAME = var.project_name }
  depends_on = [aws_iam_role_policy.mailer]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_function_event_invoke_config" "mailer" {
  function_name                = aws_lambda_function.mailer.function_name
  qualifier                    = "$LATEST"
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 21600
  destination_config {
    on_failure { destination = aws_sqs_queue.mailer_failure.arn }
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_permission" "mailer_s3" {
  statement_id   = var.mailer_s3_statement_id
  function_name  = aws_lambda_function.mailer.function_name
  action         = "lambda:InvokeFunction"
  principal      = "s3.amazonaws.com"
  source_account = var.aws_account_id
  source_arn     = aws_s3_bucket.reports.arn
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket" "reports" {
  bucket        = local.reports_bucket
  force_destroy = false
  tags          = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule { object_ownership = "BucketOwnerEnforced" }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    id     = "expire-reports"
    status = "Enabled"
    filter { prefix = "reports/" }
    expiration { days = 90 }
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket_notification" "reports" {
  bucket = aws_s3_bucket.reports.id
  lambda_function {
    # AWS assigns the old notification an ID; preserve it rather than rewriting.
    id                  = var.report_notification_id
    lambda_function_arn = aws_lambda_function.mailer.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reports/"
    filter_suffix       = ".csv"
  }
  depends_on = [aws_lambda_permission.mailer_s3, aws_lambda_function_event_invoke_config.mailer]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_s3_bucket_policy" "reports" {
  bucket = aws_s3_bucket.reports.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.reports.arn, "${aws_s3_bucket.reports.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_vpc_endpoint" "reports_s3" {
  vpc_id            = var.vpc_id
  vpc_endpoint_type = "Gateway"
  service_name      = "com.amazonaws.${var.region}.s3"
  route_table_ids   = var.route_table_ids
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PreserveExistingS3Authorization"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:*"
      Resource  = "*"
    }]
  })
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_scheduler_schedule_group" "reports" {
  name = "${var.project_name}-reports"
  tags = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_scheduler_schedule" "weekly" {
  name                         = "${var.project_name}-weekly-report"
  group_name                   = aws_scheduler_schedule_group.reports.name
  state                        = var.report_schedule_state
  schedule_expression          = "cron(0 7 ? * MON *)"
  schedule_expression_timezone = "Europe/Kyiv"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_sqs_queue.work.arn
    role_arn = aws_iam_role.scheduler.arn
    dead_letter_config { arn = aws_sqs_queue.scheduler_dlq.arn }
    retry_policy {
      maximum_event_age_in_seconds = 86400
      maximum_retry_attempts       = 3
    }
    input = "{\"source\":\"schedule\",\"scheduled_time\":\"<aws.scheduler.scheduled-time>\",\"correlation_id\":\"<aws.scheduler.execution-id>\",\"schedule_arn\":\"<aws.scheduler.schedule-arn>\",\"attempt\":\"<aws.scheduler.attempt-number>\"}"
  }
  depends_on = [aws_iam_role_policy.scheduler]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}
