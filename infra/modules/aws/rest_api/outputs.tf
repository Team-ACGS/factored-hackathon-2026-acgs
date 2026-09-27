output "url" {
  description = "HTTPS URL of the API on its custom domain"
  value       = "https://${var.domain}"
}

output "name" {
  description = "REST API name, the ApiName dimension of its CloudWatch metrics"
  value       = aws_api_gateway_rest_api.this.name
}

output "execution_arn" {
  description = "Execution ARN, the prefix of every method ARN in this API"
  value       = aws_api_gateway_rest_api.this.execution_arn
}
