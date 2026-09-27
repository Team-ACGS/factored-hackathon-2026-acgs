locals {
  notifications_timeout = 30
}

module "replies_dlq" {
  source = "../../modules/aws/sqs_queue"

  name                      = "${local.name_prefix}-replies-dlq"
  fifo                      = true
  message_retention_seconds = 1209600
}

module "replies_queue" {
  source = "../../modules/aws/sqs_queue"

  name                       = "${local.name_prefix}-replies"
  fifo                       = true
  visibility_timeout_seconds = 6 * local.notifications_timeout
  dead_letter_arn            = module.replies_dlq.arn
  max_receive_count          = 3
}

resource "aws_lambda_event_source_mapping" "notifications" {
  event_source_arn        = module.replies_queue.arn
  function_name           = module.function["notifications"].arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 10
  }
}
