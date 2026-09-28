output "name" {
  description = "Table name"
  value       = aws_dynamodb_table.this.name
}

output "arn" {
  description = "Table ARN"
  value       = aws_dynamodb_table.this.arn
}

output "stream_arn" {
  description = "ARN of the table's stream, empty when the table has none"
  value       = aws_dynamodb_table.this.stream_arn
}
