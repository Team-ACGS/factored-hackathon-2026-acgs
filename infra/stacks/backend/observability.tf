locals {
  backend_functions = concat(
    [for name in ["crud", "messages", "chat-notifier"] : module.function[name].name],
    [for fn in module.auth_function : fn.name],
  )

  dashboard_period = 300

  lambda_widget = {
    for title, spec in {
      "Lambda invocations" = { metric = "Invocations", stat = "Sum" }
      "Lambda errors"      = { metric = "Errors", stat = "Sum" }
      "Lambda duration"    = { metric = "Duration", stat = "p90" }
      "Lambda throttles"   = { metric = "Throttles", stat = "Sum" }
    } : title => spec
  }

  backend_widgets = concat(
    [
      {
        type = "metric", width = 12, height = 6
        properties = {
          title  = "API requests and errors"
          region = var.aws_region
          stat   = "Sum"
          period = local.dashboard_period
          metrics = [
            for metric in ["Count", "4XXError", "5XXError"] :
            ["AWS/ApiGateway", metric, "ApiName", module.api.name]
          ]
        }
      },
      {
        type = "metric", width = 12, height = 6
        properties = {
          title   = "API latency"
          region  = var.aws_region
          stat    = "p90"
          period  = local.dashboard_period
          metrics = [["AWS/ApiGateway", "Latency", "ApiName", module.api.name]]
        }
      },
    ],
    [
      for title, spec in local.lambda_widget : {
        type = "metric", width = 12, height = 6
        properties = {
          title   = title
          region  = var.aws_region
          stat    = spec.stat
          period  = local.dashboard_period
          metrics = [for fn in local.backend_functions : ["AWS/Lambda", spec.metric, "FunctionName", fn]]
        }
      }
    ],
    [
      {
        type = "metric", width = 12, height = 6
        properties = {
          title   = "Messages stream iterator age"
          region  = var.aws_region
          stat    = "Maximum"
          period  = local.dashboard_period
          metrics = [for name in keys(local.stream_consumers) : ["AWS/Lambda", "IteratorAge", "FunctionName", module.function[name].name]]
        }
      },
      {
        type = "metric", width = 12, height = 6
        properties = {
          title   = "Messages stream failures"
          region  = var.aws_region
          stat    = "Maximum"
          period  = local.dashboard_period
          metrics = [for dlq in module.stream_dlq : ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", dlq.name]]
        }
      },
      {
        type = "metric", width = 12, height = 6
        properties = {
          title  = "DynamoDB consumed capacity"
          region = var.aws_region
          stat   = "Sum"
          period = local.dashboard_period
          metrics = [
            for pair in setproduct(["ConsumedReadCapacityUnits", "ConsumedWriteCapacityUnits"], [for table in module.table : table.name]) :
            ["AWS/DynamoDB", pair[0], "TableName", pair[1]]
          ]
        }
      },
      {
        type = "metric", width = 24, height = 6
        properties = {
          title   = "Clara/Backend custom metrics"
          region  = var.aws_region
          stat    = "Sum"
          period  = local.dashboard_period
          metrics = [[{ expression = "SEARCH('{Clara/Backend,service}', 'Sum', ${local.dashboard_period})", id = "backend" }]]
        }
      },
    ],
  )

  assistant_widgets = concat(
    [
      for title, spec in local.lambda_widget : {
        type = "metric", width = 12, height = 6
        properties = {
          title   = "chatbot ${lower(trimprefix(title, "Lambda "))}"
          region  = var.aws_region
          stat    = spec.stat
          period  = local.dashboard_period
          metrics = [["AWS/Lambda", spec.metric, "FunctionName", module.function["chatbot"].name]]
        }
      }
    ],
    [
      for title, spec in {
        "Bedrock invocations"   = { metric = "Invocations", stat = "Sum" }
        "Bedrock latency"       = { metric = "InvocationLatency", stat = "p90" }
        "Bedrock input tokens"  = { metric = "InputTokenCount", stat = "Sum" }
        "Bedrock output tokens" = { metric = "OutputTokenCount", stat = "Sum" }
        } : {
        type = "metric", width = 12, height = 6
        properties = {
          title   = title
          region  = var.aws_region
          period  = local.dashboard_period
          metrics = [[{ expression = "SEARCH('{AWS/Bedrock,ModelId} MetricName=\"${spec.metric}\"', '${spec.stat}', ${local.dashboard_period})", id = "bedrock" }]]
        }
      }
    ],
    [
      {
        type = "metric", width = 12, height = 6
        properties = {
          title  = "Turn events delivered"
          region = var.aws_region
          stat   = "Sum"
          period = local.dashboard_period
          metrics = [
            ["AWS/Events", "MatchedEvents", "EventBusName", module.event_bus.name, "RuleName", "${module.event_bus.name}-turns"],
            ["AWS/Events", "FailedInvocations", "EventBusName", module.event_bus.name, "RuleName", "${module.event_bus.name}-turns"],
            ["AWS/Firehose", "DeliveryToS3.Records", "DeliveryStreamName", module.turn_events_stream.name],
          ]
        }
      },
      {
        type = "metric", width = 12, height = 6
        properties = {
          title   = "Clara/Assistant custom metrics"
          region  = var.aws_region
          stat    = "Sum"
          period  = local.dashboard_period
          metrics = [[{ expression = "SEARCH('{Clara/Assistant,service}', 'Sum', ${local.dashboard_period})", id = "assistant" }]]
        }
      },
    ],
  )
}

resource "aws_cloudwatch_dashboard" "backend" {
  dashboard_name = "${local.name_prefix}-backend"
  dashboard_body = jsonencode({ widgets = local.backend_widgets })
}

resource "aws_cloudwatch_dashboard" "assistant" {
  dashboard_name = "${local.name_prefix}-assistant"
  dashboard_body = jsonencode({ widgets = local.assistant_widgets })
}
