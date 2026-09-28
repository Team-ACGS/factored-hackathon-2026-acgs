locals {
  stream_consumers = {
    chat-notifier = {
      batch_size = 10
      pattern    = { eventName = ["INSERT"] }
    }

    chatbot = {
      batch_size = 1
      pattern = {
        eventName = ["INSERT"]
        dynamodb  = { NewImage = { sender_type = { S = ["customer"] } } }
      }
    }
  }
}

module "stream_dlq" {
  source   = "../../modules/aws/sqs_queue"
  for_each = local.stream_consumers

  name                      = "${local.name_prefix}-${each.key}-dlq"
  message_retention_seconds = 1209600
}

resource "aws_lambda_event_source_mapping" "messages" {
  for_each = local.stream_consumers

  event_source_arn  = module.table["messages"].stream_arn
  function_name     = module.function[each.key].arn
  starting_position = "LATEST"

  batch_size                         = each.value.batch_size
  maximum_batching_window_in_seconds = 0
  parallelization_factor             = 10
  maximum_retry_attempts             = 3
  bisect_batch_on_function_error     = true
  function_response_types            = ["ReportBatchItemFailures"]

  filter_criteria {
    filter {
      pattern = jsonencode(each.value.pattern)
    }
  }

  destination_config {
    on_failure {
      destination_arn = module.stream_dlq[each.key].arn
    }
  }
}
