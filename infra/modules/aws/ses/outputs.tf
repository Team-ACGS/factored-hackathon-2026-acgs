output "identity_arn" {
  description = "ARN of the domain identity, available only once SES has verified it"
  value       = aws_sesv2_email_identity.this.arn

  depends_on = [terraform_data.verified]
}

output "configuration_set_name" {
  description = "Default configuration set of the identity"
  value       = aws_sesv2_configuration_set.this.configuration_set_name
}

output "configuration_set_arn" {
  description = "ARN of the configuration set, required next to the identity to authorize ses:SendEmail"
  value       = aws_sesv2_configuration_set.this.arn
}
