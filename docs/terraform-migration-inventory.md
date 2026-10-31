# Terraform migration inventory

The preparation inventory remains a null-ID scope baseline. Read-only discovery
on 2026-10-27 produced a separate [observed ID inventory](terraform-live-import-inventory.json)
and [readiness assessment](terraform-migration-readiness.md). All 41 proposed
import IDs are known and now present in local imports.tf; no import, state write
or cloud change has occurred. See [the preview instructions](terraform-first-preview.md). HCP and
several read-permission checks remain blocked. Do not treat observed IDs as import
approval or set the adoption gate true.

31 CloudFormation declarations map to 41 Terraform objects (40 if Google federation
is absent). Authentication: 5; reports: 29; parser: 7. The additional ten objects
manage existing embedded IAM, queue and S3 configuration, not new AWS infrastructure.
All types document import support in the pinned provider. Planned recreations: zero.
Actual import/recreation totals must be recorded after the live phase.

| Stack | CFN declaration or embedded property | Terraform address | Import ID form |
| --- | --- | --- | --- |
| ai | InvokePermission | `aws_lambda_permission.parser_invoke` | `function_name/statement_id` |
| ai | LogGroup | `aws_cloudwatch_log_group.parser` | `log_group_name` |
| ai | Parser | `aws_lambda_function.parser` | `function_name` |
| ai | Role | `aws_iam_role.parser` | `role_name` |
| ai | Role.Policies | `aws_iam_role_policy.parser` | `role_name:policy_name` |
| ai | Url | `aws_lambda_function_url.parser` | `function_name` |
| ai | UrlPermission | `aws_lambda_permission.parser_url` | `function_name/statement_id` |
| auth | GoogleIdentityProvider | `aws_cognito_identity_provider.google[0]` | `user_pool_id:Google` |
| auth | ManagedLoginBranding | `aws_cognito_managed_login_branding.frontend` | `user_pool_id,managed_login_branding_id` |
| auth | UserPool | `aws_cognito_user_pool.main` | `user_pool_id` |
| auth | UserPoolClient | `aws_cognito_user_pool_client.frontend` | `user_pool_id/client_id` |
| auth | UserPoolDomain | `aws_cognito_user_pool_domain.main` | `domain_prefix` |
| reports | Builder | `aws_lambda_function.builder` | `function_name` |
| reports | BuilderDlq | `aws_sqs_queue.builder_dlq` | `queue_url` |
| reports | BuilderDlq.RedriveAllowPolicy | `aws_sqs_queue_redrive_allow_policy.builder_dlq` | `queue_url` |
| reports | BuilderLogGroup | `aws_cloudwatch_log_group.builder` | `log_group_name` |
| reports | BuilderMapping | `aws_lambda_event_source_mapping.builder` | `mapping_uuid` |
| reports | BuilderRole | `aws_iam_role.builder` | `role_name` |
| reports | BuilderRole.Policies | `aws_iam_role_policy.builder` | `role_name:policy_name` |
| reports | MailState | `aws_dynamodb_table.mail_state` | `table_name` |
| reports | Mailer | `aws_lambda_function.mailer` | `function_name` |
| reports | MailerAsyncConfig | `aws_lambda_function_event_invoke_config.mailer` | `function_name:$LATEST` |
| reports | MailerFailureQueue | `aws_sqs_queue.mailer_failure` | `queue_url` |
| reports | MailerLogGroup | `aws_cloudwatch_log_group.mailer` | `log_group_name` |
| reports | MailerRole | `aws_iam_role.mailer` | `role_name` |
| reports | MailerRole.Policies | `aws_iam_role_policy.mailer` | `role_name:policy_name` |
| reports | MailerS3Permission | `aws_lambda_permission.mailer_s3` | `function_name/statement_id` |
| reports | ReportsBucket | `aws_s3_bucket.reports` | `bucket_name` |
| reports | ReportsBucket.BucketEncryption | `aws_s3_bucket_server_side_encryption_configuration.reports` | `bucket_name` |
| reports | ReportsBucket.LifecycleConfiguration | `aws_s3_bucket_lifecycle_configuration.reports` | `bucket_name` |
| reports | ReportsBucket.NotificationConfiguration | `aws_s3_bucket_notification.reports` | `bucket_name` |
| reports | ReportsBucket.OwnershipControls | `aws_s3_bucket_ownership_controls.reports` | `bucket_name` |
| reports | ReportsBucket.PublicAccessBlockConfiguration | `aws_s3_bucket_public_access_block.reports` | `bucket_name` |
| reports | ReportsBucketPolicy | `aws_s3_bucket_policy.reports` | `bucket_name` |
| reports | S3Endpoint | `aws_vpc_endpoint.reports_s3` | `vpce_id` |
| reports | ScheduleGroup | `aws_scheduler_schedule_group.reports` | `group_name` |
| reports | SchedulerDlq | `aws_sqs_queue.scheduler_dlq` | `queue_url` |
| reports | SchedulerRole | `aws_iam_role.scheduler` | `role_name` |
| reports | SchedulerRole.Policies | `aws_iam_role_policy.scheduler` | `role_name:policy_name` |
| reports | WeeklySchedule | `aws_scheduler_schedule.weekly` | `group_name/schedule_name` |
| reports | WorkQueue | `aws_sqs_queue.work` | `queue_url` |

## Scope and parity review

- Every original declaration is represented. S3 encryption, ownership, public
  access, lifecycle and notifications become separate resources. IAM inline
  policies and the builder DLQ redrive allow policy are also separate.
- Names, Cognito settings, queue retention/redrive, report expiry, IAM scope,
  handler commands, memory/timeouts, CORS and event wiring follow the originals.
- The parser boundary policy is external and referenced, not adopted. The ECR
  repository, SES identities, budget, backend/Aurora/network, migration runner,
  site and GitHub OIDC stacks remain outside this migration. Existing network
  IDs are required variables, avoiding ownership of those resources.
- No new ManagedBy or Environment tags during adoption: those would change AWS.
  No versioning, new schema, new model, pricing update or schedule activation.
- No image ignore_changes: Terraform owns reporting/parser images and complete
  environments; a reviewed immutable digest update goes through HCP. GitHub
  retains the API image/deployment path and may publish artifacts for later HCP
  promotion, but does not update Terraform-managed functions.

## Required live inventory before handover

Record stack template/parameters/outputs/resources, physical names, conditional
resources, policies and tags, all three Lambda configuration/image digests,
permission Sids, bucket notification ID and every notification, Cognito schema,
client defaults/token lifetimes and branding, logging settings, endpoint routes,
queue attributes, scheduler state and payload. Compare actual values to these
files. CloudFormation stack-level tags/defaults may differ from template tags.

Check external stack exports/imports, IAM dependencies and shared endpoint usage
before deleting any stack. Preserve Cognito user identities/client/domain,
reports and deduplication state, queue messages, resource policies, notifications
and schedules. Review user/report/message counts and existing configuration
before and after the handover without publishing private data.

Provider defaults and service-normalized Cognito schemas/provider_details,
S3 lifecycle filters/transition defaults, DynamoDB encryption and Lambda logging
may require HCL reconciliation. Never hide differences with broad ignore_changes;
match the reviewed deployed configuration and require an import-only plan.

References for import forms are pinned per row in the JSON inventory, using the
[official AWS provider source](https://github.com/hashicorp/terraform-provider-aws/tree/v6.70.0/website/docs/r).
