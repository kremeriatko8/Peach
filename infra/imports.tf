# Reviewed IDs from the 2026-10-27 inventory, re-verified by HCP previews on 2026-10-29/31.
# Retain was deployed and peach-auth/peach-ai/peach-reports were deleted on 2026-10-31,
# so CloudFormation no longer owns these objects. The approved HCP apply imports them.
# Generated offline from reviewed physical IDs. No infrastructure action executed.

import {
  to = aws_lambda_permission.parser_invoke
  id = "peach-agenda-parser/peach-ai-InvokePermission-1aneGP8egfuW"
}

import {
  to = aws_cloudwatch_log_group.parser
  id = "/aws/lambda/peach-agenda-parser"
}

import {
  to = aws_lambda_function.parser
  id = "peach-agenda-parser"
}

import {
  to = aws_iam_role.parser
  id = "peach-ai-Role-VyBHkDA80Fxu"
}

import {
  to = aws_iam_role_policy.parser
  id = "peach-ai-Role-VyBHkDA80Fxu:parser"
}

import {
  to = aws_lambda_function_url.parser
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_permission.parser_url
  id = "peach-agenda-parser/peach-ai-UrlPermission-qhG0kDsGDpX5"
}

import {
  to = aws_cognito_identity_provider.google[0]
  id = "us-east-1_bs7cWxhJp:Google"
}

import {
  to = aws_cognito_managed_login_branding.frontend
  id = "us-east-1_bs7cWxhJp,aa403fbb-692c-4af3-b194-f07246c5edae"
}

import {
  to = aws_cognito_user_pool.main
  id = "us-east-1_bs7cWxhJp"
}

import {
  to = aws_cognito_user_pool_client.frontend
  id = "us-east-1_bs7cWxhJp/4vscaj9gks4n63ds52gbhi5ggn"
}

import {
  to = aws_cognito_user_pool_domain.main
  id = "peach-auth-diby4tampbgny"
}

import {
  to = aws_lambda_function.builder
  id = "peach-report-builder"
}

import {
  to = aws_sqs_queue.builder_dlq
  id = "https://sqs.us-east-1.amazonaws.com/968053399627/peach-report-builder-dlq"
}

import {
  to = aws_sqs_queue_redrive_allow_policy.builder_dlq
  id = "https://sqs.us-east-1.amazonaws.com/968053399627/peach-report-builder-dlq"
}

import {
  to = aws_cloudwatch_log_group.builder
  id = "/aws/lambda/peach-report-builder"
}

import {
  to = aws_lambda_event_source_mapping.builder
  id = "3910d1ed-06a8-4867-a77e-9192b19d8c6d"
}

import {
  to = aws_iam_role.builder
  id = "peach-report-builder"
}

import {
  to = aws_iam_role_policy.builder
  id = "peach-report-builder:report-builder"
}

import {
  to = aws_dynamodb_table.mail_state
  id = "peach-report-mail-state"
}

import {
  to = aws_lambda_function.mailer
  id = "peach-report-mailer"
}

import {
  to = aws_lambda_function_event_invoke_config.mailer
  id = "peach-report-mailer:$LATEST"
}

import {
  to = aws_sqs_queue.mailer_failure
  id = "https://sqs.us-east-1.amazonaws.com/968053399627/peach-report-mailer-failures"
}

import {
  to = aws_cloudwatch_log_group.mailer
  id = "/aws/lambda/peach-report-mailer"
}

import {
  to = aws_iam_role.mailer
  id = "peach-report-mailer"
}

import {
  to = aws_iam_role_policy.mailer
  id = "peach-report-mailer:report-mailer"
}

import {
  to = aws_lambda_permission.mailer_s3
  id = "peach-report-mailer/peach-reports-MailerS3Permission-Qbsido0QF2oJ"
}

import {
  to = aws_s3_bucket.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_s3_bucket_lifecycle_configuration.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_s3_bucket_notification.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_s3_bucket_ownership_controls.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_s3_bucket_public_access_block.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_s3_bucket_policy.reports
  id = "peach-reports-968053399627-us-east-1"
}

import {
  to = aws_vpc_endpoint.reports_s3
  id = "vpce-0e24aa58428a2f072"
}

import {
  to = aws_scheduler_schedule_group.reports
  id = "peach-reports"
}

import {
  to = aws_sqs_queue.scheduler_dlq
  id = "https://sqs.us-east-1.amazonaws.com/968053399627/peach-report-scheduler-dlq"
}

import {
  to = aws_iam_role.scheduler
  id = "peach-report-scheduler"
}

import {
  to = aws_iam_role_policy.scheduler
  id = "peach-report-scheduler:send-report-work"
}

import {
  to = aws_scheduler_schedule.weekly
  id = "peach-reports/peach-weekly-report"
}

import {
  to = aws_sqs_queue.work
  id = "https://sqs.us-east-1.amazonaws.com/968053399627/peach-report-work"
}
