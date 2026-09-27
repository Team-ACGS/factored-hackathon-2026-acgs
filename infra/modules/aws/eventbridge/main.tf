resource "aws_cloudwatch_event_bus" "this" {
  name = var.name

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_iam_role" "targets" {
  name = "${var.name}-bus-targets"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, { Name = "${var.name}-bus-targets" })
}

resource "aws_iam_role_policy" "targets" {
  name = "firehose"
  role = aws_iam_role.targets.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
      Resource = [for rule in var.firehose_rules : rule.stream_arn]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "this" {
  for_each = var.firehose_rules

  name           = "${var.name}-${each.key}"
  description    = "Delivers ${each.key} from ${var.name} to Firehose"
  event_bus_name = aws_cloudwatch_event_bus.this.name
  event_pattern  = jsonencode(each.value.pattern)

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })
}

resource "aws_cloudwatch_event_target" "this" {
  for_each = var.firehose_rules

  rule           = aws_cloudwatch_event_rule.this[each.key].name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  arn            = each.value.stream_arn
  role_arn       = aws_iam_role.targets.arn
}
