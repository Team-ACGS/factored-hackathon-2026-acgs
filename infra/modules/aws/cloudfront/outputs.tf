output "distribution_arn" {
  description = "ARN of the distribution, used by the origin bucket policy"
  value       = aws_cloudfront_distribution.this.arn
}

output "distribution_id" {
  description = "ID of the distribution, used to create invalidations"
  value       = aws_cloudfront_distribution.this.id
}

output "url" {
  description = "HTTPS URL the distribution answers on"
  value       = "https://${var.domain}"
}
