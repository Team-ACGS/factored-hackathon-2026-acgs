output "arn" {
  description = "Delivery stream ARN"
  value       = aws_kinesis_firehose_delivery_stream.this.arn
}

output "name" {
  description = "Delivery stream name, the DeliveryStreamName dimension of its metrics"
  value       = aws_kinesis_firehose_delivery_stream.this.name
}
