output "http_url" {
  description = "Endpoint a publisher POSTs to, at /event"
  value       = "https://${aws_appsync_api.this.dns["HTTP"]}/event"
}

output "realtime_url" {
  description = "WebSocket endpoint a subscriber connects to"
  value       = "wss://${aws_appsync_api.this.dns["REALTIME"]}/event/realtime"
}

output "namespace_arn" {
  description = "ARN of the channel namespace, the resource appsync:EventPublish is granted on"
  value       = "${aws_appsync_api.this.api_arn}/channelNamespace/${aws_appsync_channel_namespace.this.name}"
}

output "namespace" {
  description = "First segment of every channel path"
  value       = aws_appsync_channel_namespace.this.name
}
