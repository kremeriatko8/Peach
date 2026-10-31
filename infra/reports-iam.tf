# IAM policies translated from the original template; no permission expansion.
resource "aws_iam_role" "builder" {
  name = "${var.project_name}-report-builder"
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
  tags = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_iam_role_policy" "builder" {
  name = "report-builder"
  role = aws_iam_role.builder.id
  policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Effect"   = "Allow"
      "Action"   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      "Resource" = "${aws_cloudwatch_log_group.builder.arn}:*"
      }, {
      "Effect"   = "Allow"
      "Action"   = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSubnets", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"]
      "Resource" = "*"
      }, {
      "Effect"   = "Allow"
      "Action"   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      "Resource" = aws_sqs_queue.work.arn
      }, {
      "Effect"   = "Allow"
      "Action"   = "s3:PutObject"
      "Resource" = "arn:${local.partition}:s3:::${var.project_name}-reports-${var.aws_account_id}-${var.region}/reports/${var.report_scope_id}/*.csv"
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

resource "aws_iam_role" "mailer" {
  name = "${var.project_name}-report-mailer"
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
  tags = { PROJECT_NAME = var.project_name }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.adoption_inventory_complete
      error_message = "Live inventory and import mapping must be reviewed before planning adoption."
    }
  }
}

resource "aws_iam_role_policy" "mailer" {
  name = "report-mailer"
  role = aws_iam_role.mailer.id
  policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Effect"   = "Allow"
      "Action"   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      "Resource" = "${aws_cloudwatch_log_group.mailer.arn}:*"
      }, {
      "Effect"   = "Allow"
      "Action"   = "s3:GetObject"
      "Resource" = "arn:${local.partition}:s3:::${var.project_name}-reports-${var.aws_account_id}-${var.region}/reports/${var.report_scope_id}/*.csv"
      }, {
      "Effect"   = "Allow"
      "Action"   = ["dynamodb:UpdateItem", "dynamodb:GetItem"]
      "Resource" = aws_dynamodb_table.mail_state.arn
      }, {
      "Effect"   = "Allow"
      "Action"   = "ses:SendRawEmail"
      "Resource" = "arn:${local.partition}:ses:${var.region}:${var.aws_account_id}:identity/*"
      "Condition" = {
        "StringEquals" = {
          "ses:FromAddress" = var.report_from_email
        }
        "ForAllValues:StringEquals" = {
          "ses:Recipients" = [var.report_recipient_email]
        }
      }
      }, {
      "Effect"   = "Allow"
      "Action"   = "sqs:SendMessage"
      "Resource" = aws_sqs_queue.mailer_failure.arn
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

resource "aws_iam_role" "scheduler" {
  name = "${var.project_name}-report-scheduler"
  assume_role_policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Effect" = "Allow"
      "Principal" = {
        "Service" = "scheduler.amazonaws.com"
      }
      "Action" = "sts:AssumeRole"
      "Condition" = {
        "StringEquals" = {
          "aws:SourceAccount" = var.aws_account_id
        }
        "ArnEquals" = {
          "aws:SourceArn" = aws_scheduler_schedule_group.reports.arn
        }
      }
    }]
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

resource "aws_iam_role_policy" "scheduler" {
  name = "send-report-work"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Effect"   = "Allow"
      "Action"   = "sqs:SendMessage"
      "Resource" = [aws_sqs_queue.work.arn, aws_sqs_queue.scheduler_dlq.arn]
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
