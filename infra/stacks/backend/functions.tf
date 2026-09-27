################################################################################
# Capabilities
################################################################################

data "aws_bedrock_inference_profile" "assistant" {
  inference_profile_id = var.bedrock_inference_profile_id
}

locals {
  capability = {
    assume_customer_role = {
      actions   = ["sts:AssumeRole", "sts:TagSession"]
      resources = [local.access_role_arns.customer]
    }

    assume_staff_roles = {
      actions   = ["sts:AssumeRole"]
      resources = [local.access_role_arns.agent, local.access_role_arns.officer, local.access_role_arns.analyst]
    }

    bedrock_invoke = {
      actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
      resources = concat(
        [data.aws_bedrock_inference_profile.assistant.inference_profile_arn],
        [for model in data.aws_bedrock_inference_profile.assistant.models : model.model_arn],
      )
    }

    replies_enqueue = {
      actions   = ["sqs:SendMessage"]
      resources = [module.replies_queue.arn]
    }

    replies_consume = {
      actions = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes",
      ]
      resources = [module.replies_queue.arn]
    }

    turn_events_put = {
      actions   = ["events:PutEvents"]
      resources = [module.event_bus.arn]
    }

    messages_write = {
      actions   = ["dynamodb:PutItem"]
      resources = [module.table["messages"].arn]
    }

    rooms_update = {
      actions   = ["dynamodb:UpdateItem"]
      resources = [module.table["rooms"].arn]
    }

    realtime_publish = {
      actions   = ["appsync:EventPublish"]
      resources = [module.realtime.namespace_arn]
    }
  }

  request_env = merge(local.table_env, {
    COMPLAINTS_QUEUE_INDEX = local.complaints_queue_index
    ROLE_CUSTOMER_ARN      = local.access_role_arns.customer
    ROLE_AGENT_ARN         = local.access_role_arns.agent
    ROLE_OFFICER_ARN       = local.access_role_arns.officer
    ROLE_ANALYST_ARN       = local.access_role_arns.analyst
    CUSTOMERS_POOL_ID      = module.customers_pool.id
    STAFF_POOL_ID          = module.staff_pool.id
    CUSTOMER_CLIENT_ID     = module.customers_pool.client_ids["customer"]
    SUPPORT_CLIENT_ID      = module.staff_pool.client_ids["support"]
    BACKOFFICE_CLIENT_ID   = module.staff_pool.client_ids["backoffice"]
    REPLIES_QUEUE_URL      = module.replies_queue.url
  })

  function_defaults = {
    capabilities = []
    environment  = {}
    namespace    = "Clara/Backend"
    memory_size  = 512
    timeout      = 29
  }

  function_specs = {
    crud = {
      capabilities = ["assume_customer_role", "assume_staff_roles", "replies_enqueue"]
      environment  = local.request_env
    }

    chatbot = {
      capabilities = ["assume_customer_role", "bedrock_invoke", "replies_enqueue", "turn_events_put"]
      namespace    = "Clara/Assistant"
      memory_size  = 1024
      timeout      = 60

      environment = merge(local.request_env, {
        BEDROCK_MODEL_ID = data.aws_bedrock_inference_profile.assistant.inference_profile_id
        EVENT_BUS_NAME   = module.event_bus.name
        EVENT_SOURCE     = local.turn_event_source
      })
    }

    notifications = {
      capabilities = ["replies_consume", "messages_write", "rooms_update", "realtime_publish"]
      timeout      = local.notifications_timeout

      environment = {
        TABLE_MESSAGES     = module.table["messages"].name
        TABLE_ROOMS        = module.table["rooms"].name
        REALTIME_HTTP_URL  = module.realtime.http_url
        REALTIME_NAMESPACE = module.realtime.namespace
      }
    }
  }

  functions = {
    for name, spec in local.function_specs : name => merge(local.function_defaults, spec)
  }
}

################################################################################
# Functions
################################################################################

module "function" {
  source   = "../../modules/aws/lambda_function"
  for_each = local.functions

  name        = "${local.name_prefix}-${each.key}"
  handler     = "handler.handler"
  memory_size = each.value.memory_size
  timeout     = each.value.timeout

  artifacts_bucket = module.artifacts_bucket.id
  initial_s3_key   = aws_s3_object.bootstrap["api"].key

  environment = merge(each.value.environment, {
    POWERTOOLS_SERVICE_NAME      = each.key
    POWERTOOLS_METRICS_NAMESPACE = each.value.namespace
  })

  policy_statements = {
    for capability in each.value.capabilities : capability => local.capability[capability]
  }

  log_retention_days = var.log_retention_days
}
