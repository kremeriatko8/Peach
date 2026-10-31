resource "aws_cloudwatch_log_group" "parser" {
  name              = "/aws/lambda/${var.project_name}-agenda-parser"
  retention_in_days = 7
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_function" "parser" {
  function_name = "${var.project_name}-agenda-parser"
  package_type  = "Image"
  image_uri     = var.parser_image_uri
  image_config { command = ["app.ai.agenda_lambda.handler"] }
  architectures = [var.parser_architecture]
  role          = aws_iam_role.parser.arn
  memory_size   = 512
  timeout       = 30
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.parser.name
  }
  environment {
    variables = {
      APP_ENV                       = "production"
      COGNITO_AUTHORITY             = local.authority
      COGNITO_CLIENT_ID             = aws_cognito_user_pool_client.frontend.id
      COGNITO_JWKS_JSON             = var.cognito_jwks_json
      PARSER_MODEL                  = var.parser_model
      PARSER_ENABLED                = tostring(var.parser_enabled)
      PARSER_MAX_TOKENS             = "2048"
      PARSER_REQUESTS_PER_MINUTE    = "3"
      PARSER_INPUT_USD_PER_MILLION  = tostring(var.input_usd_per_million)
      PARSER_OUTPUT_USD_PER_MILLION = tostring(var.output_usd_per_million)
    }
  }
  depends_on = [aws_iam_role_policy.parser]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_function_url" "parser" {
  function_name      = aws_lambda_function.parser.function_name
  authorization_type = "NONE"
  cors {
    allow_origins = var.parser_frontend_origins
    allow_methods = ["POST"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 300
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_permission" "parser_url" {
  statement_id           = var.parser_url_statement_id
  function_name          = aws_lambda_function.parser.function_name
  action                 = "lambda:InvokeFunctionUrl"
  principal              = "*"
  function_url_auth_type = "NONE"
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_lambda_permission" "parser_invoke" {
  statement_id             = var.parser_invoke_statement_id
  function_name            = aws_lambda_function.parser.function_name
  action                   = "lambda:InvokeFunction"
  principal                = "*"
  invoked_via_function_url = true
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}
