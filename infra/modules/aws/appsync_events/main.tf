data "aws_region" "current" {}

resource "aws_iam_role" "logs" {
  name = "${var.name}-appsync-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "appsync.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, { Name = "${var.name}-appsync-logs" })
}

resource "aws_iam_role_policy" "logs" {
  name = "logs"
  role = aws_iam_role.logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.this.arn}:*"
    }]
  })
}

resource "aws_appsync_api" "this" {
  name = var.name

  event_config {
    auth_provider {
      auth_type = "AWS_IAM"
    }

    dynamic "auth_provider" {
      for_each = var.cognito_user_pool_ids

      content {
        auth_type = "AMAZON_COGNITO_USER_POOLS"

        cognito_config {
          user_pool_id = auth_provider.value
          aws_region   = data.aws_region.current.region
        }
      }
    }

    connection_auth_mode {
      auth_type = "AWS_IAM"
    }

    connection_auth_mode {
      auth_type = "AMAZON_COGNITO_USER_POOLS"
    }

    default_publish_auth_mode {
      auth_type = "AWS_IAM"
    }

    default_subscribe_auth_mode {
      auth_type = "AMAZON_COGNITO_USER_POOLS"
    }

    log_config {
      cloudwatch_logs_role_arn = aws_iam_role.logs.arn
      log_level                = "ERROR"
    }
  }

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/appsync/apis/${aws_appsync_api.this.api_id}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_appsync_channel_namespace" "this" {
  name          = var.namespace
  api_id        = aws_appsync_api.this.api_id
  code_handlers = var.code_handlers

  publish_auth_mode {
    auth_type = "AWS_IAM"
  }

  subscribe_auth_mode {
    auth_type = "AMAZON_COGNITO_USER_POOLS"
  }

  tags = merge(var.tags, { Name = "${var.name}-${var.namespace}" })
}
