output "id" {
  description = "User pool id"
  value       = aws_cognito_user_pool.this.id
}

output "arn" {
  description = "User pool ARN"
  value       = aws_cognito_user_pool.this.arn
}

output "client_ids" {
  description = "App client id per web"
  value       = { for name, client in aws_cognito_user_pool_client.this : name => client.id }
}
