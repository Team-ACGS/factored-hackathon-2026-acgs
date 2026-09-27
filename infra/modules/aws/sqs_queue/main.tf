resource "aws_sqs_queue" "this" {
  name                        = var.fifo ? "${var.name}.fifo" : var.name
  fifo_queue                  = var.fifo ? true : null
  content_based_deduplication = var.fifo ? false : null
  visibility_timeout_seconds  = var.visibility_timeout_seconds
  message_retention_seconds   = var.message_retention_seconds
  sqs_managed_sse_enabled     = true

  redrive_policy = var.dead_letter_arn == null ? null : jsonencode({
    deadLetterTargetArn = var.dead_letter_arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(var.tags, { Name = var.name })
}
