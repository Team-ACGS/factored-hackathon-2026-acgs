output "arn" {
  description = "Queue ARN"
  value       = aws_sqs_queue.this.arn
}

output "url" {
  description = "Queue URL"
  value       = aws_sqs_queue.this.url
}

output "name" {
  description = "Queue name"
  value       = aws_sqs_queue.this.name
}
