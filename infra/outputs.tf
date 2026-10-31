# Public allowlisted compatibility outputs only. Never output secrets or environments.
output "auth_outputs" {
  description = "Public auth values, preserving the former CloudFormation output contract."
  value = {
    UserPoolId                       = aws_cognito_user_pool.main.id
    UserPoolClientId                 = aws_cognito_user_pool_client.frontend.id
    CognitoDomainPrefix              = var.cognito_domain_prefix
    CognitoDomain                    = local.cognito_domain
    Authority                        = local.authority
    GoogleAuthorizedJavaScriptOrigin = local.cognito_domain
    GoogleAuthorizedRedirectUri      = "${local.cognito_domain}/oauth2/idpresponse"
    FrontendCallbackUrl              = "${var.frontend_origin}/auth/callback/"
    LocalhostCallbackUrl             = "${var.localhost_origin}/auth/callback/"
    FrontendLogoutUrl                = "${var.frontend_origin}/"
    LocalhostLogoutUrl               = "${var.localhost_origin}/"
    GoogleFederationEnabled          = tostring(var.google_enabled)
  }
}

output "reports_outputs" {
  description = "Public reports values, preserving the former CloudFormation output contract."
  value = {
    WorkQueueUrl          = aws_sqs_queue.work.url
    WorkQueueArn          = aws_sqs_queue.work.arn
    BuilderDlqUrl         = aws_sqs_queue.builder_dlq.url
    SchedulerDlqUrl       = aws_sqs_queue.scheduler_dlq.url
    MailerFailureQueueUrl = aws_sqs_queue.mailer_failure.url
    ReportsBucketName     = aws_s3_bucket.reports.bucket
    BuilderFunctionName   = aws_lambda_function.builder.function_name
    MailerFunctionName    = aws_lambda_function.mailer.function_name
    ScheduleName          = aws_scheduler_schedule.weekly.name
    ScheduleGroupName     = aws_scheduler_schedule_group.reports.name
    MailStateTableName    = aws_dynamodb_table.mail_state.name
  }
}

output "ai_outputs" {
  description = "Public ai values, preserving the former CloudFormation output contract."
  value = {
    ParserUrl    = aws_lambda_function_url.parser.function_url
    FunctionName = aws_lambda_function.parser.function_name
  }
}

output "cognito_authority" {
  value = local.authority
}
output "cognito_client_id" {
  value = aws_cognito_user_pool_client.frontend.id
}
output "cognito_domain" {
  value = local.cognito_domain
}
output "parser_url" {
  value = aws_lambda_function_url.parser.function_url
}
output "report_queue_url" {
  value = aws_sqs_queue.work.url
}
output "reports_bucket_name" {
  value = aws_s3_bucket.reports.bucket
}
