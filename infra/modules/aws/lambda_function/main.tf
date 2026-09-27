resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_iam_role" "this" {
  name = var.name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_iam_role_policy" "runtime" {
  name = "runtime"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.this.arn}:*"
      },
      {
        Sid      = "Tracing"
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy" "access" {
  count = length(var.policy_statements) > 0 ? 1 : 0

  name = "access"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      for sid, statement in var.policy_statements : {
        Sid      = replace(title(replace(sid, "_", " ")), " ", "")
        Effect   = "Allow"
        Action   = statement.actions
        Resource = statement.resources
      }
    ]
  })
}

resource "aws_lambda_function" "this" {
  function_name = var.name
  role          = aws_iam_role.this.arn
  handler       = var.handler
  runtime       = var.runtime
  architectures = ["x86_64"]
  memory_size   = var.memory_size
  timeout       = var.timeout

  s3_bucket = var.artifacts_bucket
  s3_key    = var.initial_s3_key

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.this.name
  }

  tracing_config {
    mode = "Active"
  }

  dynamic "environment" {
    for_each = length(var.environment) > 0 ? [var.environment] : []

    content {
      variables = environment.value
    }
  }

  tags = merge(var.tags, { Name = var.name })

  lifecycle {
    ignore_changes = [s3_key, s3_object_version, source_code_hash, publish]
  }

  depends_on = [aws_iam_role_policy.runtime]
}
