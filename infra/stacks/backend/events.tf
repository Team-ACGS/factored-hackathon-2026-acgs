locals {
  turn_event_source = "clara.chatbot"
}

module "events_bucket" {
  source = "../../modules/aws/s3"

  name          = "${local.name_prefix}-events${local.bucket_suffix}"
  force_destroy = true
}

module "turn_events_stream" {
  source = "../../modules/aws/firehose"

  name               = "${local.name_prefix}-turn-events"
  bucket_arn         = module.events_bucket.arn
  prefix             = "turns"
  log_retention_days = var.log_retention_days
}

module "event_bus" {
  source = "../../modules/aws/eventbridge"

  name = local.name_prefix

  firehose_rules = {
    turns = {
      pattern    = { source = [local.turn_event_source] }
      stream_arn = module.turn_events_stream.arn
    }
  }
}
