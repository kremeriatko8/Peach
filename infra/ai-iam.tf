# IAM policies translated from the original template; no permission expansion.
resource "aws_iam_role" "parser" {
  name = var.parser_role_name
  assume_role_policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Effect" = "Allow"
      "Principal" = {
        "Service" = "lambda.amazonaws.com"
      }
      "Action" = "sts:AssumeRole"
    }]
  })
  permissions_boundary = "arn:aws:iam::${var.aws_account_id}:policy/PeachAgendaParserBoundary"
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_iam_role_policy" "parser" {
  name = "parser"
  role = aws_iam_role.parser.id
  policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Effect"   = "Allow"
      "Action"   = "bedrock:InvokeModel"
      "Resource" = var.inference_resource_arn
      }, {
      "Effect"   = "Allow"
      "Action"   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      "Resource" = "${aws_cloudwatch_log_group.parser.arn}:*"
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
