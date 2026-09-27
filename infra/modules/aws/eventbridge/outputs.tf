output "name" {
  description = "Event bus name, the EventBusName of every PutEvents call"
  value       = aws_cloudwatch_event_bus.this.name
}

output "arn" {
  description = "Event bus ARN, the resource events:PutEvents is granted on"
  value       = aws_cloudwatch_event_bus.this.arn
}
