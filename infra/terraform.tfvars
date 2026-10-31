# Existing Peach environment: public settings observed 2026-10-27.
# See docs/terraform-live-input-worksheet.json for provenance. Refresh before handover.
# Secrets and other intentionally omitted inputs remain required workspace variables.
# No active imports exist. Keep the adoption gate false until migration review.
adoption_inventory_complete         = false
project_name                        = "peach"
region                              = "us-east-1"
aws_account_id                      = "968053399627"
cognito_domain_prefix               = "peach-auth-diby4tampbgny"
frontend_origin                     = "https://diby4tampbgny.cloudfront.net"
localhost_origin                    = "http://localhost:3000"
google_enabled                      = true
cognito_email_constraints           = { "min_length" : "0", "max_length" : "2048" }
reports_image_uri                   = "968053399627.dkr.ecr.us-east-1.amazonaws.com/peach-backend@sha256:ac2d47b04a705075df2e2c09fc0106c771f423fae008d7a7df2d775541935629"
parser_image_uri                    = "968053399627.dkr.ecr.us-east-1.amazonaws.com/peach-backend@sha256:8bac6eded73b84a482bf307b4694ab7151ecc5ec3533701739872cbff8036da6"
reports_architecture                = "arm64"
parser_architecture                 = "arm64"
vpc_id                              = "vpc-0def9c995c9c73f75"
subnet_ids                          = ["subnet-0ce865e3d6a942f32", "subnet-03563e6593c729e87", "subnet-0b155a6dfcdf112f6", "subnet-0d85830f27e1de8a8", "subnet-05cb823b915b8c589"]
route_table_ids                     = ["rtb-0fb1d48c2f3f092c2"]
backend_function_security_group_ids = ["sg-0545f0ff2d3d0ad76"]
report_scope_id                     = "efc72484-50e1-4111-b405-4da7c06428a8"
allow_direct_events                 = false
report_schedule_state               = "ENABLED"
parser_role_name                    = "peach-ai-Role-VyBHkDA80Fxu"
parser_enabled                      = true
parser_frontend_origins             = ["https://diby4tampbgny.cloudfront.net"]
parser_model                        = "amazon.nova-lite-v1:0"
inference_resource_arn              = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0"
input_usd_per_million               = 0.06
output_usd_per_million              = 0.24
mailer_s3_statement_id              = "peach-reports-MailerS3Permission-Qbsido0QF2oJ"
parser_url_statement_id             = "peach-ai-UrlPermission-qhG0kDsGDpX5"
parser_invoke_statement_id          = "peach-ai-InvokePermission-1aneGP8egfuW"
report_notification_id              = "N2JlZWExZTktODc0Yy00OGI1LTkyODUtOTJiNTBkNzQ4Njc1"
