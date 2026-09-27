resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/kinesisfirehose/${var.name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_cloudwatch_log_stream" "delivery" {
  name           = "DestinationDelivery"
  log_group_name = aws_cloudwatch_log_group.this.name
}

resource "aws_iam_role" "this" {
  name = "${var.name}-firehose"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, { Name = "${var.name}-firehose" })
}

resource "aws_iam_role_policy" "this" {
  name = "delivery"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteObjects"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject",
        ]
        Resource = [var.bucket_arn, "${var.bucket_arn}/*"]
      },
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.this.arn}:*"
      },
    ]
  })
}

resource "aws_kinesis_firehose_delivery_stream" "this" {
  name        = var.name
  destination = "extended_s3"

  server_side_encryption {
    enabled  = true
    key_type = "AWS_OWNED_CMK"
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.this.arn
    bucket_arn          = var.bucket_arn
    prefix              = "${var.prefix}/!{timestamp:yyyy}/!{timestamp:MM}/!{timestamp:dd}/"
    error_output_prefix = "errors/${var.prefix}/!{firehose:error-output-type}/!{timestamp:yyyy}/!{timestamp:MM}/!{timestamp:dd}/"
    compression_format  = "GZIP"
    buffering_interval  = var.buffering_interval_seconds
    buffering_size      = 5

    processing_configuration {
      enabled = true

      processors {
        type = "AppendDelimiterToRecord"
      }
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.this.name
      log_stream_name = aws_cloudwatch_log_stream.delivery.name
    }
  }

  tags = merge(var.tags, { Name = var.name })

  depends_on = [aws_iam_role_policy.this]
}
